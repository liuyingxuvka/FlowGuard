"""Validate and project the authored reverse-surface map for model inputs.

The current authority joins and reverse-owner receipts are derived evidence.
They are checked by their own lifecycle and must not make the model that
refreshes them depend on its own output. This module keeps that derived state
out of the exact semantic-map input while still validating the map's complete
authoring checksum before any projection is accepted.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from pathlib import PurePosixPath
import re
import stat
from typing import Any, Mapping


IMPLEMENTATION_SURFACE_MAP_PATH = (
    ".flowguard/structure/reverse-surfaces/implementation-surface-map.json"
)
CURRENT_SURFACE_DISCOVERY_PATH = (
    ".flowguard/structure/reverse-surfaces/current-discovery.json"
)
CURRENT_SURFACE_DISCOVERY_SCHEMA = "flowguard.implementation_surface_audit.v1"
IMPLEMENTATION_SURFACE_MAP_SCHEMA = "flowguard.implementation_surface_map.v1"
IMPLEMENTATION_SURFACE_AUTHORING_SCHEMA = (
    "flowguard.implementation_surface_semantic_authoring.v1"
)

_SURFACE_DISPOSITIONS = frozenset(
    {
        "governed",
        "internal_proven",
        "retired_proven",
        "not_applicable_proven",
        "blocked_gap",
    }
)
_OBLIGATION_DISPOSITIONS = frozenset(
    {
        "governed",
        "model_only_proven",
        "retired_proven",
        "not_applicable_proven",
        "blocked_gap",
    }
)
_SHA256_IDENTITY = re.compile(r"^sha256:[0-9a-f]{64}$")

_DERIVED_MODEL_INPUT_FIELDS = frozenset(
    {
        "authoring_fingerprint",
        "authoring_status",
        "current_authority_join",
        "current_behavior_ledger_join",
        "current_revision",
        "discovery_fingerprint",
        "owner_receipt_identities",
    }
)


class ReverseSurfaceMapIdentityError(ValueError):
    """Raised when the reverse-surface map cannot provide a current identity."""


def require_regular_repository_file(root: str | Path, relative_path: str) -> Path:
    """Resolve one project file while rejecting linked/reparse components."""

    normalized = str(relative_path or "").replace("\\", "/")
    relative = PurePosixPath(normalized)
    if (
        not normalized
        or relative.is_absolute()
        or ".." in relative.parts
        or "." in relative.parts
    ):
        raise ReverseSurfaceMapIdentityError(
            f"repository evidence path must be a normalized relative path: {relative_path!r}"
        )
    root_path = Path(root).resolve()
    if not root_path.is_dir():
        raise ReverseSurfaceMapIdentityError(
            f"repository evidence root is not a directory: {root_path}"
        )
    current = root_path
    parts = relative.parts
    for index, part in enumerate(parts):
        current = current / part
        try:
            metadata = current.lstat()
        except OSError as exc:
            raise ReverseSurfaceMapIdentityError(
                f"repository evidence file is missing or inaccessible: {current}"
            ) from exc
        if current.is_symlink() or bool(
            getattr(metadata, "st_file_attributes", 0) & 0x0400
        ):
            raise ReverseSurfaceMapIdentityError(
                f"repository evidence path crosses a symlink or reparse point: {current}"
            )
        is_last = index == len(parts) - 1
        expected_mode = stat.S_ISREG if is_last else stat.S_ISDIR
        if not expected_mode(metadata.st_mode):
            kind = "regular file" if is_last else "directory"
            raise ReverseSurfaceMapIdentityError(
                f"repository evidence component is not a {kind}: {current}"
            )
    try:
        current.resolve(strict=True).relative_to(root_path)
    except (OSError, ValueError) as exc:
        raise ReverseSurfaceMapIdentityError(
            "repository evidence path escapes repository root"
        ) from exc
    return current


def require_regular_implementation_surface_map(root: str | Path) -> Path:
    """Return the exact map path after rejecting links in every path component."""

    return require_regular_repository_file(root, IMPLEMENTATION_SURFACE_MAP_PATH)


def _current_discovery_fingerprint(root: str | Path) -> str:
    path = require_regular_repository_file(root, CURRENT_SURFACE_DISCOVERY_PATH)
    payload = _read_reverse_surface_map_payload(path)
    if not isinstance(payload, Mapping):
        raise ReverseSurfaceMapIdentityError(
            "current reverse discovery must be an object"
        )
    if payload.get("schema_version") != CURRENT_SURFACE_DISCOVERY_SCHEMA:
        raise ReverseSurfaceMapIdentityError(
            "current reverse discovery schema is not current"
        )
    if payload.get("status") != "passed":
        raise ReverseSurfaceMapIdentityError(
            "current reverse discovery is not a passing observation"
        )
    fingerprint = str(payload.get("discovery_fingerprint", "")).strip()
    if not _SHA256_IDENTITY.fullmatch(fingerprint):
        raise ReverseSurfaceMapIdentityError(
            "current reverse discovery fingerprint is invalid"
        )
    source_paths = payload.get("source_paths")
    surfaces = payload.get("surfaces")
    if (
        not isinstance(source_paths, list)
        or not source_paths
        or not isinstance(surfaces, list)
        or not surfaces
        or payload.get("surface_count") != len(surfaces)
    ):
        raise ReverseSurfaceMapIdentityError(
            "current reverse discovery denominator is incomplete"
        )
    return fingerprint


def _load_current_reverse_surface_map(
    root: str | Path,
    *,
    expected_discovery_fingerprint: str | None = None,
) -> Mapping[str, Any]:
    path = require_regular_implementation_surface_map(root)
    payload = load_reverse_surface_map_payload(path)
    current_discovery = (
        str(expected_discovery_fingerprint).strip()
        if expected_discovery_fingerprint is not None
        else _current_discovery_fingerprint(root)
    )
    if payload.get("discovery_fingerprint") != current_discovery:
        raise ReverseSurfaceMapIdentityError(
            "implementation surface map discovery fingerprint is stale"
        )
    return payload


def load_current_reverse_surface_map_model_input_projection(
    root: str | Path,
) -> dict[str, Any]:
    """Load the current map and reject a map tied to another discovery."""

    payload = _load_current_reverse_surface_map(root)
    return _model_input_projection_validated(payload)


def load_current_reverse_surface_map_with_semantic_fingerprint(
    root: str | Path,
    *,
    expected_discovery_fingerprint: str | None = None,
) -> tuple[Mapping[str, Any], str]:
    """Load one current map and derive its semantic fingerprint in one pass."""

    payload = _load_current_reverse_surface_map(
        root,
        expected_discovery_fingerprint=expected_discovery_fingerprint,
    )
    return payload, _canonical_hash(_model_input_projection_validated(payload))


def load_current_reverse_owner_semantic_map_fingerprint(
    root: str | Path,
    *,
    expected_discovery_fingerprint: str | None = None,
) -> str:
    """Fingerprint a map only after binding it to the current discovery."""

    _payload, fingerprint = load_current_reverse_surface_map_with_semantic_fingerprint(
        root,
        expected_discovery_fingerprint=expected_discovery_fingerprint,
    )
    return fingerprint


def _canonical_hash(value: Any) -> str:
    encoded = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def validate_reverse_surface_map_payload(value: Any) -> Mapping[str, Any]:
    """Validate the v1 map structure and checksum over all authored bytes."""

    if not isinstance(value, Mapping):
        raise ReverseSurfaceMapIdentityError(
            "implementation surface map must be an object"
        )
    if value.get("schema_version") != IMPLEMENTATION_SURFACE_MAP_SCHEMA:
        raise ReverseSurfaceMapIdentityError(
            "implementation surface map schema is not current"
        )
    declared = str(value.get("authoring_fingerprint", "")).strip()
    if not declared.startswith("sha256:"):
        raise ReverseSurfaceMapIdentityError(
            "implementation surface map authoring fingerprint is missing or invalid"
        )
    expected = _canonical_hash(
        {str(key): raw for key, raw in value.items() if str(key) != "authoring_fingerprint"}
    )
    if declared != expected:
        raise ReverseSurfaceMapIdentityError(
            "implementation surface map authoring fingerprint is stale"
        )
    required_text = (
        "inventory_id",
        "project_boundary",
        "current_revision",
        "discovery_fingerprint",
        "claim_boundary",
        "authoring_schema",
        "authoring_status",
        "semantic_authority",
        "no_fallback_policy",
    )
    for field in required_text:
        raw = value.get(field)
        if not isinstance(raw, str) or not raw.strip():
            raise ReverseSurfaceMapIdentityError(
                f"implementation surface map field {field} must be a non-empty string"
            )
    if value.get("authoring_schema") != IMPLEMENTATION_SURFACE_AUTHORING_SCHEMA:
        raise ReverseSurfaceMapIdentityError(
            "implementation surface map authoring schema is not current"
        )
    if not _SHA256_IDENTITY.fullmatch(str(value.get("discovery_fingerprint", ""))):
        raise ReverseSurfaceMapIdentityError(
            "implementation surface map discovery fingerprint is invalid"
        )

    surfaces = _require_array(value, "surfaces", context="implementation surface map")
    groups = _require_array(
        value, "component_groups", context="implementation surface map"
    )
    obligations = _require_array(
        value, "model_obligations", context="implementation surface map"
    )
    if not surfaces and not groups:
        raise ReverseSurfaceMapIdentityError(
            "implementation surface map must contain surfaces or component groups"
        )
    _require_string_array(
        value.get("terminal_receipt_refs"),
        context="implementation surface map.terminal_receipt_refs",
    )
    for join_name in ("current_authority_join", "current_behavior_ledger_join"):
        if join_name in value and not isinstance(value[join_name], Mapping):
            raise ReverseSurfaceMapIdentityError(
                f"implementation surface map {join_name} must be an object"
            )
    if "owner_receipt_identities" in value:
        identities = _require_array(
            value,
            "owner_receipt_identities",
            context="implementation surface map",
        )
        if any(not isinstance(row, Mapping) for row in identities):
            raise ReverseSurfaceMapIdentityError(
                "implementation surface map owner_receipt_identities rows must be objects"
            )

    seen_surface_ids: set[str] = set()
    for index, row in enumerate(surfaces):
        _validate_surface_row(row, context=f"surfaces[{index}]")
        surface_id = str(row["surface_id"])
        if surface_id in seen_surface_ids:
            raise ReverseSurfaceMapIdentityError(
                f"implementation surface map duplicates surface_id {surface_id!r}"
            )
        seen_surface_ids.add(surface_id)

    seen_group_ids: set[str] = set()
    for index, row in enumerate(groups):
        _validate_component_group_row(row, context=f"component_groups[{index}]")
        group_id = str(row["review_group_id"])
        if group_id in seen_group_ids:
            raise ReverseSurfaceMapIdentityError(
                f"implementation surface map duplicates review_group_id {group_id!r}"
            )
        seen_group_ids.add(group_id)

    seen_obligation_ids: set[str] = set()
    for index, row in enumerate(obligations):
        _validate_obligation_row(row, context=f"model_obligations[{index}]")
        obligation_id = str(row["obligation_id"])
        if obligation_id in seen_obligation_ids:
            raise ReverseSurfaceMapIdentityError(
                f"implementation surface map duplicates obligation_id {obligation_id!r}"
            )
        seen_obligation_ids.add(obligation_id)
    return value


def _require_array(
    mapping: Mapping[str, Any], field: str, *, context: str
) -> list[Any]:
    value = mapping.get(field)
    if not isinstance(value, list):
        raise ReverseSurfaceMapIdentityError(f"{context}.{field} must be an array")
    return value


def _require_text(value: Any, *, context: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ReverseSurfaceMapIdentityError(
            f"implementation surface map {context} must be a non-empty string"
        )
    return value


def _require_string_array(value: Any, *, context: str, nonempty: bool = False) -> list[str]:
    if not isinstance(value, list):
        raise ReverseSurfaceMapIdentityError(f"implementation surface map {context} must be an array")
    result = [
        _require_text(item, context=f"{context}[{index}]")
        for index, item in enumerate(value)
    ]
    if nonempty and not result:
        raise ReverseSurfaceMapIdentityError(
            f"implementation surface map {context} must not be empty"
        )
    if len(result) != len(set(result)):
        raise ReverseSurfaceMapIdentityError(
            f"implementation surface map {context} contains duplicates"
        )
    return result


def _validate_semantic_row(
    row: Any,
    *,
    context: str,
    required_text: tuple[str, ...],
    required_arrays: tuple[str, ...],
    nonempty_arrays: tuple[str, ...] = (),
    optional_text: tuple[str, ...],
    optional_arrays: tuple[str, ...],
) -> Mapping[str, Any]:
    if not isinstance(row, Mapping):
        raise ReverseSurfaceMapIdentityError(
            f"implementation surface map {context} must be an object"
        )
    for field in required_text:
        _require_text(row.get(field), context=f"{context}.{field}")
    for field in required_arrays:
        _require_string_array(
            row.get(field),
            context=f"{context}.{field}",
            nonempty=field in nonempty_arrays,
        )
    for field in optional_text:
        if field in row:
            _require_text(row[field], context=f"{context}.{field}")
    for field in optional_arrays:
        if field in row:
            _require_string_array(
                row[field], context=f"{context}.{field}"
            )
    return row


def _validate_surface_row(row: Any, *, context: str) -> None:
    surface = _validate_semantic_row(
        row,
        context=context,
        required_text=(
            "surface_id",
            "surface_kind",
            "surface_class",
            "review_group_id",
            "review_granularity",
            "disposition",
            "owner",
        ),
        required_arrays=("test_refs", "receipt_refs"),
        nonempty_arrays=("test_refs",),
        optional_text=(
            "source_path",
            "source_ref",
            "source_fingerprint",
            "intent_id",
            "model_owner_id",
            "proof_ref",
            "reason",
            "gap_reason",
            "not_applicable_reason",
            "owner_receipt_id",
            "owner_receipt_fingerprint",
        ),
        optional_arrays=("model_obligation_ids", "test_owner_ids", "proof_refs"),
    )
    if surface["disposition"] not in _SURFACE_DISPOSITIONS:
        raise ReverseSurfaceMapIdentityError(
            f"implementation surface map {context}.disposition is not current"
        )
    if surface["review_granularity"] not in {"surface", "component"}:
        raise ReverseSurfaceMapIdentityError(
            f"implementation surface map {context}.review_granularity is invalid"
        )
    if "source_fingerprint" in surface and not _SHA256_IDENTITY.fullmatch(
        str(surface["source_fingerprint"])
    ):
        raise ReverseSurfaceMapIdentityError(
            f"implementation surface map {context}.source_fingerprint is invalid"
        )
    disposition = surface["disposition"]
    if disposition in {"governed", "internal_proven"}:
        _require_text(surface.get("intent_id"), context=f"{context}.intent_id")
        _require_text(
            surface.get("model_owner_id"), context=f"{context}.model_owner_id"
        )
        _require_string_array(
            surface.get("model_obligation_ids"),
            context=f"{context}.model_obligation_ids",
            nonempty=True,
        )
    if disposition != "blocked_gap" and not surface["receipt_refs"]:
        raise ReverseSurfaceMapIdentityError(
            f"implementation surface map {context}.receipt_refs must not be empty"
        )
    if disposition == "internal_proven":
        _require_text(surface.get("proof_ref"), context=f"{context}.proof_ref")
        _require_text(surface.get("reason"), context=f"{context}.reason")
    elif disposition == "blocked_gap":
        _require_text(surface.get("gap_reason"), context=f"{context}.gap_reason")
    elif disposition in {"retired_proven", "not_applicable_proven"}:
        _require_text(surface.get("proof_ref"), context=f"{context}.proof_ref")
        _require_text(surface.get("reason"), context=f"{context}.reason")
        if disposition == "not_applicable_proven":
            _require_text(
                surface.get("not_applicable_reason"),
                context=f"{context}.not_applicable_reason",
            )


def _validate_component_group_row(row: Any, *, context: str) -> None:
    group = _validate_semantic_row(
        row,
        context=context,
        required_text=(
            "review_group_id",
            "review_granularity",
            "disposition",
            "owner",
        ),
        required_arrays=("surface_ids", "test_refs", "receipt_refs"),
        nonempty_arrays=("surface_ids", "test_refs"),
        optional_text=(
            "intent_id",
            "model_owner_id",
            "proof_ref",
            "reason",
            "gap_reason",
            "not_applicable_reason",
            "owner_receipt_id",
            "owner_receipt_fingerprint",
        ),
        optional_arrays=("model_obligation_ids", "test_owner_ids", "proof_refs"),
    )
    if group["review_granularity"] != "component":
        raise ReverseSurfaceMapIdentityError(
            f"implementation surface map {context}.review_granularity must be component"
        )
    if group["disposition"] not in _SURFACE_DISPOSITIONS:
        raise ReverseSurfaceMapIdentityError(
            f"implementation surface map {context}.disposition is not current"
        )
    if group["disposition"] in {"governed", "internal_proven"}:
        _require_text(group.get("intent_id"), context=f"{context}.intent_id")
        _require_text(group.get("model_owner_id"), context=f"{context}.model_owner_id")
        _require_string_array(
            group.get("model_obligation_ids"),
            context=f"{context}.model_obligation_ids",
            nonempty=True,
        )
    if group["disposition"] != "blocked_gap" and not group["receipt_refs"]:
        raise ReverseSurfaceMapIdentityError(
            f"implementation surface map {context}.receipt_refs must not be empty"
        )
    if group["disposition"] == "internal_proven":
        _require_text(group.get("proof_ref"), context=f"{context}.proof_ref")
        _require_text(group.get("reason"), context=f"{context}.reason")
    elif group["disposition"] == "blocked_gap":
        _require_text(group.get("gap_reason"), context=f"{context}.gap_reason")
    elif group["disposition"] in {"retired_proven", "not_applicable_proven"}:
        _require_text(group.get("proof_ref"), context=f"{context}.proof_ref")
        _require_text(group.get("reason"), context=f"{context}.reason")
        if group["disposition"] == "not_applicable_proven":
            _require_text(
                group.get("not_applicable_reason"),
                context=f"{context}.not_applicable_reason",
            )


def _validate_obligation_row(row: Any, *, context: str) -> None:
    obligation = _validate_semantic_row(
        row,
        context=context,
        required_text=("obligation_id", "disposition"),
        required_arrays=("surface_ids",),
        nonempty_arrays=(),
        optional_text=(
            "intent_id",
            "model_owner_id",
            "proof_ref",
            "reason",
            "gap_reason",
        ),
        optional_arrays=(),
    )
    if obligation["disposition"] not in _OBLIGATION_DISPOSITIONS:
        raise ReverseSurfaceMapIdentityError(
            f"implementation surface map {context}.disposition is not current"
        )
    if obligation["disposition"] == "governed":
        _require_string_array(
            obligation["surface_ids"],
            context=f"{context}.surface_ids",
            nonempty=True,
        )
        _require_text(obligation.get("intent_id"), context=f"{context}.intent_id")
        _require_text(
            obligation.get("model_owner_id"), context=f"{context}.model_owner_id"
        )
    elif obligation["disposition"] == "blocked_gap":
        if obligation["surface_ids"]:
            raise ReverseSurfaceMapIdentityError(
                f"implementation surface map {context}.surface_ids must be empty for blocked_gap"
            )
        _require_text(obligation.get("gap_reason"), context=f"{context}.gap_reason")
    else:
        if obligation["surface_ids"]:
            raise ReverseSurfaceMapIdentityError(
                f"implementation surface map {context}.surface_ids must be empty for typed proof"
            )
        _require_text(obligation.get("proof_ref"), context=f"{context}.proof_ref")
        _require_text(obligation.get("reason"), context=f"{context}.reason")


def _unique_object_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ReverseSurfaceMapIdentityError(
                f"implementation surface map duplicates JSON field {key!r}"
            )
        result[key] = value
    return result


def load_reverse_surface_map_payload(path: str | Path) -> Mapping[str, Any]:
    """Read one map without accepting duplicate JSON fields or stale hashes."""

    candidate = Path(path)
    return validate_reverse_surface_map_payload(_read_reverse_surface_map_payload(candidate))


def _read_reverse_surface_map_payload(path: Path) -> Any:
    """Parse one map while rejecting duplicate JSON object keys."""

    try:
        return json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_unique_object_pairs,
        )
    except ReverseSurfaceMapIdentityError:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ReverseSurfaceMapIdentityError(
            f"cannot parse implementation surface map: {path}"
        ) from exc


def _is_generated_owner_receipt_reference(value: Any) -> bool:
    """Classify the canonical producer path and typed owner-receipt anchor.

    This is identity projection only. The currentness audit still resolves and
    verifies every generated reference; a matching string is never evidence.
    Non-owner references and malformed lookalikes remain authored inputs.
    """

    if not isinstance(value, str):
        return False
    path_text, separator, anchor = value.partition("#")
    if (
        not separator
        or not path_text
        or path_text.startswith("/")
        or chr(92) in path_text
        or ":" in path_text
        or any(part in {"", ".", ".."} for part in path_text.split("/"))
    ):
        return False
    if re.fullmatch(
        r"receipt:validation-owner:[^:#/\s]+:[0-9a-f]{32}", anchor
    ) is None:
        return False
    # Reuse the actual producer's pure filename rule. A typed anchor in an
    # ordinary proof file must remain an authored reference, not generated I/O.
    from .evidence_receipts import _receipt_filename

    return PurePosixPath(path_text).name == _receipt_filename(anchor)


def owner_binding_projection(value: Mapping[str, Any]) -> dict[str, Any]:
    """Project only the defined top-level and row-level generated fields.

    Unknown authored extensions remain identity even when an extension uses a
    field name that is reserved elsewhere in the v1 map. Non-owner proof and
    test receipt references also remain in their authored order.
    """

    projected = dict(value)
    for field in (
        "authoring_fingerprint",
        "owner_receipt_identities",
        "current_authority_join",
        "current_behavior_ledger_join",
    ):
        projected.pop(field, None)

    for collection_name in ("surfaces", "component_groups"):
        rows = projected.get(collection_name)
        if not isinstance(rows, list):
            continue
        projected_rows: list[dict[str, Any]] = []
        for row in rows:
            # The caller validates row shape before projecting.
            projected_row = dict(row)
            projected_row.pop("owner_receipt_id", None)
            projected_row.pop("owner_receipt_fingerprint", None)
            receipt_refs = projected_row.get("receipt_refs")
            if isinstance(receipt_refs, list):
                projected_row["receipt_refs"] = [
                    item
                    for item in receipt_refs
                    if not _is_generated_owner_receipt_reference(item)
                ]
            projected_rows.append(projected_row)
        projected[collection_name] = projected_rows

    terminal_receipts = projected.get("terminal_receipt_refs")
    if isinstance(terminal_receipts, list):
        projected["terminal_receipt_refs"] = [
            item
            for item in terminal_receipts
            if not _is_generated_owner_receipt_reference(item)
        ]
    return projected


def _model_input_projection_validated(value: Mapping[str, Any]) -> dict[str, Any]:
    projected = owner_binding_projection(value)
    for key in _DERIVED_MODEL_INPUT_FIELDS:
        projected.pop(key, None)
    return projected


def load_reverse_surface_map_model_input_projection(
    path: str | Path,
) -> dict[str, Any]:
    """Load, validate and project a map in one schema/checksum pass."""

    candidate = Path(path)
    payload = validate_reverse_surface_map_payload(
        _read_reverse_surface_map_payload(candidate)
    )
    return _model_input_projection_validated(payload)


def load_reverse_owner_semantic_map_fingerprint(path: str | Path) -> str:
    """Load, validate and fingerprint map semantics in one schema/checksum pass."""

    candidate = Path(path)
    payload = validate_reverse_surface_map_payload(
        _read_reverse_surface_map_payload(candidate)
    )
    return _canonical_hash(_model_input_projection_validated(payload))


def model_input_projection(value: Any) -> dict[str, Any]:
    """Return semantic surface/owner/test bindings without derived currentness.

    Surface rows, component membership, model obligations, intent/owner/test
    bindings, proof references, and unknown authored fields remain identity.
    Current discovery/revision markers, owner receipt identities, and both
    currentness joins are verified by their own gates and are omitted here.
    """

    payload = validate_reverse_surface_map_payload(value)
    return _model_input_projection_validated(payload)


def reverse_owner_semantic_map_fingerprint(value: Any) -> str:
    """Fingerprint the current authored map semantics for reverse-owner contracts.

    The complete raw authoring checksum is validated first. Currentness joins,
    status, revision and discovery markers use their own current evidence
    bindings; owner contracts separately bind authority head/snapshot/revision/
    activation, discovery, owner routes, model parent and child receipts. The
    shared semantic projection keeps those generated identities out of this
    map-derived input while retaining authored surface/owner/intent/test/proof
    semantics.
    """

    payload = validate_reverse_surface_map_payload(value)
    return _canonical_hash(_model_input_projection_validated(payload))


__all__ = [
    "IMPLEMENTATION_SURFACE_MAP_PATH",
    "IMPLEMENTATION_SURFACE_MAP_SCHEMA",
    "ReverseSurfaceMapIdentityError",
    "load_reverse_surface_map_payload",
    "load_reverse_surface_map_model_input_projection",
    "load_reverse_owner_semantic_map_fingerprint",
    "load_current_reverse_surface_map_model_input_projection",
    "load_current_reverse_surface_map_with_semantic_fingerprint",
    "load_current_reverse_owner_semantic_map_fingerprint",
    "model_input_projection",
    "owner_binding_projection",
    "require_regular_repository_file",
    "require_regular_implementation_surface_map",
    "validate_reverse_surface_map_payload",
    "reverse_owner_semantic_map_fingerprint",
]
