"""Durable project model authority, pointer-last activation, and audit."""

from __future__ import annotations

from dataclasses import dataclass, replace
import json
from pathlib import Path, PurePosixPath, PureWindowsPath
import re
import tomllib
from typing import Any, Iterable, Mapping

from .model_authority import (
    LIFECYCLE_ACTIVE,
    REVISION_ACCEPTED,
    ROLLBACK_RESULT_FORWARD_REPAIR,
    SUBJECT_OBSERVED_IMPLEMENTATION,
    ModelActivationReceipt,
    ModelAuthorityError,
    ModelAuthorityHead,
    ModelRevisionSet,
    ModelRollbackContract,
    ModelRollbackReceipt,
    ModelSystemSnapshot,
    canonical_fingerprint,
    load_model_system_snapshot,
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
from .project_manifest import (
    ProjectManifestError,
    manifest_text_fingerprint,
    project_manifest_lock,
    read_manifest_text,
    replace_project_manifest_locked,
)


MODEL_AUTHORITY_SECTION = "model_authority"
MODEL_AUTHORITY_STATUS_PASS = "pass"
MODEL_AUTHORITY_STATUS_PASS_WITH_GAPS = "pass_with_gaps"
MODEL_AUTHORITY_STATUS_BLOCKED = "blocked"
_SECTION_RE = re.compile(
    r"(?ms)^\[model_authority\]\s*\n.*?(?=^\[[^\]]+\]\s*$|\Z)"
)


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
    return f".flowguard/model-mesh/snapshots/{digest}.json"


def _write_immutable_json(
    root: Path,
    category: str,
    fingerprint: str,
    payload: Mapping[str, Any],
) -> Path:
    digest = fingerprint.split(":", 1)[1]
    path = root / ".flowguard" / "model-mesh" / category / f"{digest}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(
        payload,
        ensure_ascii=False,
        allow_nan=False,
        indent=2,
        sort_keys=True,
    ) + "\n"
    if path.exists():
        if path.read_text(encoding="utf-8") != text:
            raise ModelAuthorityError(
                f"immutable {category} path contains different bytes"
            )
        return path
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(text, encoding="utf-8")
    temporary.replace(path)
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
        / "model-mesh"
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
            path.read_text(encoding="utf-8"),
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
        snapshot = load_model_system_snapshot(path)
    except (OSError, ModelAuthorityError, ValueError) as exc:
        raise ModelAuthorityError(
            f"authority ancestry snapshot is invalid: {exc}"
        ) from exc
    if snapshot.fingerprint != fingerprint:
        raise ModelAuthorityError(
            "authority ancestry snapshot does not match its content address"
        )
    return snapshot


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
        path.parents[3],
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
    mesh_root = root / ".flowguard" / "model-mesh"
    candidates: list[ModelAuthorityHead] = []
    for path in (mesh_root / "activations").glob("*.json"):
        fingerprint = f"sha256:{path.stem}"
        try:
            receipt = _load_activation_receipt(root, fingerprint)
            if (
                receipt.system_id != system_id
                or receipt.next_generation != generation
            ):
                continue
            candidates.append(
                ModelAuthorityHead(
                    system_id=receipt.system_id,
                    snapshot_fingerprint=(
                        receipt.candidate_snapshot_fingerprint
                    ),
                    subject_revision=receipt.subject_revision,
                    generation=receipt.next_generation,
                    accepted_revision_set_fingerprint=(
                        receipt.revision_set_fingerprint
                    ),
                    previous_snapshot_fingerprint=(
                        receipt.previous_snapshot_fingerprint
                    ),
                    activation_receipt_fingerprint=fingerprint,
                )
            )
        except ModelAuthorityError:
            continue
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
            root / ".flowguard" / "model-mesh" / "bootstraps"
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
    *,
    allow_legacy_path_quality_upgrade: bool = False,
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
        / "model-mesh"
        / "revisions"
        / f"{digest}.json"
    )
    upgrade_source = False
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
        if not allow_legacy_path_quality_upgrade:
            raise ModelAuthorityError(
                f"accepted revision-set artifact is invalid: {exc}"
            ) from exc
        # This import is deliberately lazy.  The builder already owns the
        # one upgrade-only conversion and imports this store for normal
        # current reads; keeping the bridge lazy avoids a module cycle and
        # prevents the retired schema from becoming a runtime reader.
        from .model_revision_builder import (
            _migrate_legacy_path_quality_revision_for_build,
        )

        revision_set = _migrate_legacy_path_quality_revision_for_build(
            root,
            head,
            snapshot,
        )
        if revision_set is None:
            raise ModelAuthorityError(
                f"accepted revision-set artifact is invalid: {exc}"
            ) from exc
        upgrade_source = True
    if revision_set.fingerprint != fingerprint and not upgrade_source:
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
        / "model-mesh"
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
    *,
    allow_legacy_path_quality_upgrade: bool = False,
) -> CurrentModelAuthorityState:
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
            allow_legacy_path_quality_upgrade=allow_legacy_path_quality_upgrade,
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
        return CurrentModelAuthorityState(
            head=head,
            snapshot=snapshot,
            accepted_revision=revision_set,
            transition_kind="activation",
            predecessor_head=predecessor,
            activation_receipt=receipt,
            verified_source_identities=(
                revision_set.current_effective_intent_view.verified_source_identities
            ),
        )

    rollback_receipt = _load_rollback_receipt(root, fingerprint)
    rollback_contract = _load_rollback_contract(
        root,
        rollback_receipt.contract_fingerprint,
    )
    predecessor = _find_exact_predecessor_head(
        root,
        system_id=head.system_id,
        generation=head.generation - 1,
        expected_fingerprint=rollback_contract.expected_head_fingerprint,
    )
    if rollback_receipt.result == ROLLBACK_RESULT_FORWARD_REPAIR:
        raise ModelAuthorityError(
            "forward-repair receipt cannot establish a new authority head"
        )
    base_snapshot = _load_snapshot_by_fingerprint(
        root,
        rollback_contract.from_snapshot_fingerprint,
    )
    _validate_revision_intent_activation(
        root,
        predecessor,
        base_snapshot,
        snapshot,
        revision_set,
        reverify_sources=False,
        allow_legacy_path_quality_upgrade=allow_legacy_path_quality_upgrade,
    )
    expected_receipt = validate_operational_rollback(
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
    if expected_receipt != rollback_receipt:
        raise ModelAuthorityError(
            "current rollback receipt is not exactly reproducible"
        )
    activation_head, _synthetic_receipt = validate_activation_plan(
        predecessor,
        base_snapshot,
        snapshot,
        revision_set,
        live_candidate_snapshot=snapshot,
        receipt_id=f"authority-audit:{rollback_receipt.receipt_id}",
    )
    expected_head = replace(
        activation_head,
        accepted_revision_set_fingerprint=revision_set.fingerprint,
        activation_receipt_fingerprint=rollback_receipt.fingerprint,
    )
    if expected_head != head:
        raise ModelAuthorityError(
            "current rollback transition does not produce the exact authority head"
        )
    return CurrentModelAuthorityState(
        head=head,
        snapshot=snapshot,
        accepted_revision=revision_set,
        transition_kind="rollback",
        predecessor_head=predecessor,
        rollback_contract=rollback_contract,
        rollback_receipt=rollback_receipt,
        verified_source_identities=(
            revision_set.current_effective_intent_view.verified_source_identities
        ),
    )


def load_current_model_authority_state(
    root: str | Path,
    *,
    head: ModelAuthorityHead | None = None,
    snapshot: ModelSystemSnapshot | None = None,
    allow_legacy_bootstrap_source: bool = False,
    reverify_current_sources: bool = False,
    allow_legacy_path_quality_upgrade: bool = False,
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

    legacy_path_quality_upgrade = False
    if allow_legacy_path_quality_upgrade:
        digest = head.accepted_revision_set_fingerprint.split(":", 1)[1]
        revision_path = (
            root_path
            / ".flowguard"
            / "model-mesh"
            / "revisions"
            / f"{digest}.json"
        )
        try:
            revision_payload = json.loads(
                revision_path.read_text(encoding="utf-8"),
                object_pairs_hook=_reject_duplicate_json_keys,
            )
        except (OSError, json.JSONDecodeError, ModelAuthorityError):
            revision_payload = None
        if isinstance(revision_payload, Mapping):
            path_rows = (
                *(
                    revision_payload.get("path_quality_subjects", ())
                    if isinstance(
                        revision_payload.get("path_quality_subjects", ()),
                        list,
                    )
                    else ()
                ),
                *(
                    revision_payload.get("path_quality_results", ())
                    if isinstance(
                        revision_payload.get("path_quality_results", ()),
                        list,
                    )
                    else ()
                ),
            )
            legacy_path_quality_upgrade = bool(
                path_rows
                and all(
                    isinstance(item, Mapping)
                    and item.get("schema_version")
                    == "flowguard.model-path-quality.v1"
                    for item in path_rows
                )
            )
    revision_set = _load_accepted_revision_set(
        root_path,
        head,
        snapshot,
        allow_legacy_path_quality_upgrade=allow_legacy_path_quality_upgrade,
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
    if legacy_path_quality_upgrade:
        # The retired revision is an explicit upgrade input, not a current
        # schema.  Its content-addressed bytes and head pointer were checked
        # by the migration helper; the new activation will immediately
        # replace this source with a current-format revision.  Do not pretend
        # that the migrated fingerprint was the historical receipt identity.
        state = CurrentModelAuthorityState(
            head=head,
            snapshot=snapshot,
            accepted_revision=revision_set,
            transition_kind="legacy_path_quality_upgrade",
            verified_source_identities=verified_sources,
        )
    else:
        state = _validate_current_typed_transition(
            root_path,
            head,
            snapshot,
            revision_set,
            # A current v5 head may have an immutable predecessor whose
            # path-quality rows were produced by the retired v1 producer.
            # Only the explicit audit/upgrade caller may normalize that
            # predecessor in memory; ordinary current reads remain strict.
            allow_legacy_path_quality_upgrade=allow_legacy_path_quality_upgrade,
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
    allow_legacy_path_quality_upgrade: bool = False,
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
        allow_legacy_path_quality_upgrade=allow_legacy_path_quality_upgrade,
    )
    return state.accepted_revision


def load_observed_model_system(
    root: str | Path,
) -> tuple[ModelAuthorityHead, ModelSystemSnapshot]:
    root_path = Path(root).resolve()
    text = read_manifest_text(root_path / ".flowguard" / "project.toml")
    return _load_observed_from_manifest_text(root_path, text)


def _load_observed_from_manifest_text(
    root_path: Path,
    text: str,
) -> tuple[ModelAuthorityHead, ModelSystemSnapshot]:
    section = _section(text)
    head = _head_from_section(section)
    relative = _relative_path(
        section["observed_snapshot_path"],
        "observed_snapshot_path",
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
                # The audit replays the immutable predecessor chain.  Permit
                # the versioned direct-to-current path-quality upgrader for
                # retired historical rows, while normal runtime loading keeps
                # the current-only reader boundary.
                allow_legacy_path_quality_upgrade=True,
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
            root_path / ".flowguard" / "model-regression-manifest.json"
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


def _validate_revision_intent_activation(
    root: Path,
    current_head: ModelAuthorityHead,
    base_snapshot: ModelSystemSnapshot,
    candidate_snapshot: ModelSystemSnapshot,
    revision_set: ModelRevisionSet,
    *,
    reverify_sources: bool = True,
    current_state: CurrentModelAuthorityState | None = None,
    allow_legacy_path_quality_upgrade: bool = False,
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

            manifest_path = root / ".flowguard" / "model-regression-manifest.json"
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
            allow_legacy_path_quality_upgrade=allow_legacy_path_quality_upgrade,
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
    *,
    receipt_id: str,
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
            # A one-time activation may consume the exact retired nested
            # path-quality projection through the explicit upgrade bridge.
            # Ordinary reads remain strict and do not enable this flag.
            allow_legacy_path_quality_upgrade=True,
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

        live_candidate = build_manifest_model_system_snapshot(
            root_path,
            snapshot_id=candidate_snapshot.snapshot_id,
            system_id=candidate_snapshot.system_id,
            subject_lane=candidate_snapshot.subject_lane,
            lifecycle=candidate_snapshot.lifecycle,
        )
        next_head, receipt = validate_activation_plan(
            current_head,
            base_snapshot,
            candidate_snapshot,
            revision_set,
            live_candidate_snapshot=live_candidate,
            receipt_id=receipt_id,
        )
        write_content_addressed_snapshot(root_path, candidate_snapshot)
        _write_immutable_json(
            root_path,
            "revisions",
            revision_set.fingerprint,
            revision_set.to_dict(),
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

        live_candidate = build_manifest_model_system_snapshot(
            root_path,
            snapshot_id=candidate_snapshot.snapshot_id,
            system_id=candidate_snapshot.system_id,
            subject_lane=candidate_snapshot.subject_lane,
            lifecycle=candidate_snapshot.lifecycle,
        )
        next_head, _ = validate_activation_plan(
            current_head,
            current_snapshot,
            candidate_snapshot,
            reverse_revision_set,
            live_candidate_snapshot=live_candidate,
            receipt_id=f"reverse-activation:{receipt_id}",
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
        _write_immutable_json(
            root_path,
            "rollbacks",
            receipt.fingerprint,
            {**receipt.to_dict(), "fingerprint": receipt.fingerprint},
        )
        next_head = replace(
            next_head,
            accepted_revision_set_fingerprint=reverse_revision_set.fingerprint,
            activation_receipt_fingerprint=receipt.fingerprint,
        )
        final_live_candidate = build_manifest_model_system_snapshot(
            root_path,
            snapshot_id=candidate_snapshot.snapshot_id,
            system_id=candidate_snapshot.system_id,
            subject_lane=candidate_snapshot.subject_lane,
            lifecycle=candidate_snapshot.lifecycle,
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
    "MODEL_AUTHORITY_STATUS_BLOCKED",
    "MODEL_AUTHORITY_STATUS_PASS",
    "MODEL_AUTHORITY_STATUS_PASS_WITH_GAPS",
    "CurrentModelAuthorityState",
    "ModelAuthorityAuditReport",
    "ModelAuthorityFinding",
    "activate_model_revision_set",
    "audit_model_authority",
    "bootstrap_model_authority",
    "load_current_accepted_revision_set",
    "load_current_model_authority_state",
    "load_observed_model_system",
    "render_model_authority_section",
    "replace_model_authority_section",
    "rollback_observed_model_system",
]
