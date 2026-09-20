"""Selective, fingerprint-checked reads over a normalized blueprint index."""

from __future__ import annotations

from collections import deque
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from functools import cached_property
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
from typing import Any

from .blueprint_topology import TOPOLOGY_RELATION_KINDS
from .evidence_receipts import fingerprint_value
from .software_blueprint_readiness import (
    BEHAVIOR_COVERAGE_REFERENCE_SHARD_KIND,
    BEHAVIOR_COVERAGE_REFERENCE_SHARD_SCHEMA,
)
from .target_system_blueprint import (
    BlueprintGapRef,
    BlueprintLayerResult,
    ModelPathQualityBlueprintBinding,
    BlueprintNativeReportRef,
    BlueprintReadinessLedger,
)


AFFECTED_BLUEPRINT_READER_SCHEMA = "flowguard.affected_blueprint_reader.v3"
AFFECTED_BLUEPRINT_INDEX_SCHEMA = "flowguard.affected_blueprint_index.v3"
AFFECTED_BLUEPRINT_UNDERSTANDING_SCHEMA = (
    "flowguard.affected_blueprint_understanding.v3"
)
AFFECTED_TASK_CONTEXT_SCHEMA = "flowguard.affected_task_context.v1"
AFFECTED_IMPACT_PLAN_SCHEMA = "flowguard.affected_impact_plan.v1"
AFFECTED_IMPACT_OWNER_DISPOSITIONS = (
    "execute",
    "reuse_current",
    "blocked",
)
AFFECTED_TOPOLOGY_INVALIDATION_EDGE_SCHEMA = (
    "flowguard.affected_topology_invalidation_edge.v1"
)
AFFECTED_TOPOLOGY_INVALIDATION_KINDS = frozenset(
    {
        "ancestor",
        "affected_sibling",
        "child",
        "cross_boundary_support",
        "delegates_to",
        "feedback",
        "produces_for",
        "repair",
        "relation_consumer",
        "relation_producer",
        "realization_member",
        "realization_owner",
        "retry",
        "shared_resource",
        "sibling",
        "supports",
    }
)
_TOPOLOGY_RELATION_INVALIDATION_DIRECTIONS = {
    "produces_for": "producer_to_consumer",
    "delegates_to": "consumer_to_producer",
    "supports": "producer_to_consumer",
    "cross_boundary_support": "producer_to_consumer",
    "feedback": "producer_to_consumer",
    "retry": "producer_to_consumer",
    "repair": "producer_to_consumer",
    "shared_resource": "producer_to_consumer",
    "affected_sibling": "producer_to_consumer",
}


class AffectedBlueprintReadError(ValueError):
    """Raised when an affected read cannot preserve normalized authority."""


class _JsonArrayRowLocator:
    """Index one canonical shard without materializing its row values.

    Canonical projection shards are envelope objects whose ``payload`` is an
    array of rows.  The generic projection loader intentionally materializes
    that array for its exhaustive integrity claim, but an affected read must
    not do so merely to discover the one row in its closure.  This locator
    memory-maps the shard, validates the JSON delimiters and row identities,
    and keeps byte offsets for the selected row value (or whole row).  JSON is
    decoded only when a caller asks for a selected field/row.
    """

    def __init__(
        self,
        path: Path,
        context: str,
        *,
        row_key: str,
        value_key: str | None,
        exact_row_fields: bool = True,
        preindexed_offsets: Mapping[str, tuple[int, int]] | None = None,
    ) -> None:
        self.path = path
        self.context = context
        self.row_key = row_key
        self.value_key = value_key
        self.exact_row_fields = exact_row_fields
        self.preindexed_offsets = (
            dict(preindexed_offsets) if preindexed_offsets is not None else None
        )
        self._handle = None
        self._mapping = None
        self._started = False
        self._field_offsets: dict[str, tuple[int, int]] | None = None
        self._row_offsets: dict[str, tuple[int, int]] | None = None
        self._cache: dict[str, Any] = {}

    @staticmethod
    def _is_whitespace(byte: int) -> bool:
        return byte in (9, 10, 13, 32)

    def _open(self) -> None:
        if self._started:
            return
        self._started = True
        try:
            if self.path.is_symlink():
                raise ValueError(f"{self.context} must not be a symlink")
            self._handle = self.path.open("rb")
            import mmap

            self._mapping = mmap.mmap(
                self._handle.fileno(), 0, access=mmap.ACCESS_READ
            )
        except (OSError, ValueError) as exc:
            mapping = self._mapping
            handle = self._handle
            self._mapping = None
            self._handle = None
            self._started = False
            self._field_offsets = None
            self._row_offsets = None
            self._cache.clear()
            if mapping is not None:
                mapping.close()
            if handle is not None:
                handle.close()
            raise AffectedBlueprintReadError(
                f"projection_read_error: cannot open {self.context}: {exc}"
            ) from exc

    def _skip_whitespace(self, position: int, limit: int) -> int:
        assert self._mapping is not None
        while position < limit and self._is_whitespace(self._mapping[position]):
            position += 1
        return position

    def _scan_string_end(self, start: int, limit: int) -> int:
        assert self._mapping is not None
        if start >= limit or self._mapping[start] != ord('"'):
            raise AffectedBlueprintReadError(
                f"projection_schema_invalid: {self.context} contains a non-string key"
            )
        position = start + 1
        escaped = False
        while position < limit:
            byte = self._mapping[position]
            if escaped:
                escaped = False
            elif byte == ord('\\'):
                escaped = True
            elif byte == ord('"'):
                return position + 1
            elif byte < 0x20:
                raise AffectedBlueprintReadError(
                    f"projection_schema_invalid: {self.context} contains a control byte"
                )
            position += 1
        raise AffectedBlueprintReadError(
            f"projection_schema_invalid: {self.context} contains an unterminated string"
        )

    def _scan_value_end(self, start: int, limit: int) -> int:
        assert self._mapping is not None
        start = self._skip_whitespace(start, limit)
        if start >= limit:
            raise AffectedBlueprintReadError(
                f"projection_schema_invalid: {self.context} ends before a value"
            )
        first = self._mapping[start]
        if first == ord('"'):
            return self._scan_string_end(start, limit)
        if first in (ord('{'), ord('[')):
            stack = [first]
            position = start + 1
            escaped = False
            in_string = False
            while position < limit:
                byte = self._mapping[position]
                if in_string:
                    if escaped:
                        escaped = False
                    elif byte == ord('\\'):
                        escaped = True
                    elif byte == ord('"'):
                        in_string = False
                    elif byte < 0x20:
                        raise AffectedBlueprintReadError(
                            f"projection_schema_invalid: {self.context} contains a control byte"
                        )
                else:
                    if byte == ord('"'):
                        in_string = True
                    elif byte in (ord('{'), ord('[')):
                        stack.append(byte)
                    elif byte in (ord('}'), ord(']')):
                        expected = ord('}') if stack[-1] == ord('{') else ord(']')
                        if byte != expected:
                            raise AffectedBlueprintReadError(
                                f"projection_schema_invalid: {self.context} has mismatched JSON delimiters"
                            )
                        stack.pop()
                        if not stack:
                            return position + 1
                position += 1
            raise AffectedBlueprintReadError(
                f"projection_schema_invalid: {self.context} contains an unterminated value"
            )

        position = start
        while position < limit and self._mapping[position] not in (
            ord(','),
            ord('}'),
            ord(']'),
        ) and not self._is_whitespace(self._mapping[position]):
            position += 1
        if position == start:
            raise AffectedBlueprintReadError(
                f"projection_schema_invalid: {self.context} contains an empty value"
            )
        return position

    def _decode(self, start: int, end: int) -> Any:
        try:
            if self._mapping is not None:
                raw = bytes(self._mapping[start:end])
            else:
                if self.path.is_symlink():
                    raise ValueError(f"{self.context} must not be a symlink")
                with self.path.open("rb") as handle:
                    handle.seek(start)
                    raw = handle.read(end - start)
            value = raw.decode("utf-8")

            def reject_duplicate_keys(
                pairs: list[tuple[str, object]],
            ) -> dict[str, object]:
                result: dict[str, object] = {}
                for key, item in pairs:
                    if key in result:
                        raise ValueError(f"duplicate JSON key: {key}")
                    result[key] = item
                return result

            return json.loads(value, object_pairs_hook=reject_duplicate_keys)
        except (UnicodeError, json.JSONDecodeError, ValueError) as exc:
            raise AffectedBlueprintReadError(
                f"projection_schema_invalid: invalid JSON in {self.context}: {exc}"
            ) from exc

    def _release_mapping(self) -> None:
        """Keep offsets but release Windows file handles after indexing."""

        mapping = self._mapping
        handle = self._handle
        self._mapping = None
        self._handle = None
        self._started = False
        if mapping is not None:
            mapping.close()
        if handle is not None:
            handle.close()

    def _scan_object_members(
        self, start: int, end: int
    ) -> dict[str, tuple[int, int]]:
        assert self._mapping is not None
        position = self._skip_whitespace(start, end)
        if position >= end or self._mapping[position] != ord('{'):
            raise AffectedBlueprintReadError(
                f"projection_schema_invalid: {self.context} row must be an object"
            )
        position += 1
        members: dict[str, tuple[int, int]] = {}
        while True:
            position = self._skip_whitespace(position, end)
            if position >= end:
                raise AffectedBlueprintReadError(
                    f"projection_schema_invalid: {self.context} object is unterminated"
                )
            if self._mapping[position] == ord('}'):
                if self._skip_whitespace(position + 1, end) != end:
                    raise AffectedBlueprintReadError(
                        f"projection_schema_invalid: {self.context} object has trailing data"
                    )
                return members
            key_end = self._scan_string_end(position, end)
            key = self._decode(position, key_end)
            if not isinstance(key, str) or key in members:
                raise AffectedBlueprintReadError(
                    f"projection_identity_mismatch: {self.context} has a duplicate or invalid key"
                )
            position = self._skip_whitespace(key_end, end)
            if position >= end or self._mapping[position] != ord(':'):
                raise AffectedBlueprintReadError(
                    f"projection_schema_invalid: {self.context} is missing ':'"
                )
            value_start = self._skip_whitespace(position + 1, end)
            value_end = self._scan_value_end(value_start, end)
            members[key] = (value_start, value_end)
            position = self._skip_whitespace(value_end, end)
            if position >= end or self._mapping[position] not in (
                ord(','),
                ord('}'),
            ):
                raise AffectedBlueprintReadError(
                    f"projection_schema_invalid: {self.context} has an invalid separator"
                )
            if self._mapping[position] == ord('}'):
                if self._skip_whitespace(position + 1, end) != end:
                    raise AffectedBlueprintReadError(
                        f"projection_schema_invalid: {self.context} object has trailing data"
                    )
                return members
            position += 1

    def _build_index(self) -> None:
        if self._row_offsets is not None:
            return
        self._open()
        assert self._mapping is not None
        root_end = len(self._mapping)
        fields = self._scan_object_members(0, root_end)
        expected_fields = {
            "schema_version",
            "shard_id",
            "kind",
            "relative_path",
            "member_ids",
            "payload",
            "content_fingerprint",
        }
        if set(fields) != expected_fields:
            raise AffectedBlueprintReadError(
                f"projection_schema_invalid: {self.context} envelope fields are not exact-current"
            )
        payload_start, payload_end = fields["payload"]
        payload_start = self._skip_whitespace(payload_start, payload_end)
        if (
            payload_start >= payload_end
            or self._mapping[payload_start] != ord('[')
        ):
            raise AffectedBlueprintReadError(
                f"projection_schema_invalid: {self.context} payload is not an array"
            )
        self._field_offsets = fields
        if self.preindexed_offsets is not None:
            payload_start = self._skip_whitespace(payload_start, payload_end)
            payload_end = self._skip_whitespace(payload_end - 1, payload_end) + 1
            for key, (row_start, row_end) in self.preindexed_offsets.items():
                if not isinstance(key, str) or not key:
                    raise AffectedBlueprintReadError(
                        f"projection_identity_mismatch: {self.context} lookup id is invalid"
                    )
                if (
                    not isinstance(row_start, int)
                    or not isinstance(row_end, int)
                    or row_start < payload_start
                    or row_end <= row_start
                    or row_end > payload_end
                ):
                    raise AffectedBlueprintReadError(
                        f"projection_identity_mismatch: {self.context} lookup offset is out of range"
                    )
            self._row_offsets = dict(self.preindexed_offsets)
            self._release_mapping()
            return
        position = payload_start + 1
        offsets: dict[str, tuple[int, int]] = {}
        while True:
            position = self._skip_whitespace(position, payload_end)
            if position >= payload_end:
                raise AffectedBlueprintReadError(
                    f"projection_schema_invalid: {self.context} payload is unterminated"
                )
            if self._mapping[position] == ord(']'):
                if self._skip_whitespace(position + 1, payload_end) != payload_end:
                    raise AffectedBlueprintReadError(
                        f"projection_schema_invalid: {self.context} payload has trailing data"
                    )
                self._row_offsets = offsets
                self._release_mapping()
                return
            row_start = position
            row_end = self._scan_value_end(row_start, payload_end)
            row_fields = self._scan_object_members(row_start, row_end)
            expected_row_fields = {self.row_key}
            if self.value_key is not None:
                expected_row_fields.add(self.value_key)
            row_fields_valid = (
                set(row_fields) == expected_row_fields
                if self.exact_row_fields
                else expected_row_fields.issubset(row_fields)
            )
            if not row_fields_valid:
                raise AffectedBlueprintReadError(
                    f"projection_schema_invalid: {self.context} row fields are not exact-current"
                )
            key = self._decode(*row_fields[self.row_key])
            if not isinstance(key, str) or not key:
                raise AffectedBlueprintReadError(
                    f"projection_identity_mismatch: {self.context} row key is invalid"
                )
            if key in offsets:
                raise AffectedBlueprintReadError(
                    f"projection_identity_mismatch: duplicate {self.row_key}: {key}"
                )
            offsets[key] = (row_start, row_end)
            position = self._skip_whitespace(row_end, payload_end)
            if position >= payload_end or self._mapping[position] not in (
                ord(','),
                ord(']'),
            ):
                raise AffectedBlueprintReadError(
                    f"projection_schema_invalid: {self.context} payload has an invalid separator"
                )
            if self._mapping[position] == ord(']'):
                if self._skip_whitespace(position + 1, payload_end) != payload_end:
                    raise AffectedBlueprintReadError(
                        f"projection_schema_invalid: {self.context} payload has trailing data"
                    )
                self._row_offsets = offsets
                self._release_mapping()
                return
            position += 1

    def field_names(self) -> tuple[str, ...]:
        self._build_index()
        assert self._field_offsets is not None
        return tuple(sorted(self._field_offsets))

    def load_field(self, name: str) -> Any:
        self._build_index()
        assert self._field_offsets is not None
        offsets = self._field_offsets.get(str(name))
        if offsets is None:
            raise KeyError(str(name))
        return self._decode(*offsets)

    def raw_field_fingerprint(self, name: str) -> str:
        """Fingerprint one envelope field without decoding its JSON value."""

        self._build_index()
        assert self._field_offsets is not None
        offsets = self._field_offsets.get(str(name))
        if offsets is None:
            raise KeyError(str(name))
        start, end = offsets
        if self.path.is_symlink():
            raise AffectedBlueprintReadError(
                f"projection_path_traversal: {self.context} must not be a symlink"
            )
        with self.path.open("rb") as handle:
            handle.seek(start)
            payload = handle.read(end - start)
        return "sha256:" + hashlib.sha256(payload).hexdigest()

    def row_keys(self) -> tuple[str, ...]:
        self._build_index()
        assert self._row_offsets is not None
        return tuple(sorted(self._row_offsets))

    def row_offsets(self) -> dict[str, tuple[int, int]]:
        self._build_index()
        assert self._row_offsets is not None
        return dict(self._row_offsets)

    def load(self, key: str) -> Any:
        key = str(key)
        if key in self._cache:
            return self._cache[key]
        self._build_index()
        assert self._row_offsets is not None
        offsets = self._row_offsets.get(key)
        if offsets is None:
            raise KeyError(key)
        row = self._decode(*offsets)
        if not isinstance(row, Mapping) or str(row.get(self.row_key, "")) != key:
            raise AffectedBlueprintReadError(
                f"projection_identity_mismatch: {self.context} lookup points to another row: {key}"
            )
        if self.value_key is None:
            value = row
        else:
            if self.value_key not in row:
                raise AffectedBlueprintReadError(
                    f"projection_schema_invalid: {self.context} selected row has no {self.value_key}"
                )
            value = row[self.value_key]
        self._cache[key] = value
        return value

    def close(self) -> None:
        mapping = self._mapping
        handle = self._handle
        self._mapping = None
        self._handle = None
        self._started = False
        self._field_offsets = None
        self._row_offsets = None
        self._cache.clear()
        if mapping is not None:
            mapping.close()
        if handle is not None:
            handle.close()

    def __del__(self) -> None:  # pragma: no cover - best-effort cleanup
        try:
            self.close()
        except Exception:
            pass


def _impact_sha256(value: Any, *, context: str) -> str:
    """Require a content-addressed identity on the affected boundary."""

    if not isinstance(value, str) or not re.fullmatch(r"sha256:[0-9a-f]{64}", value):
        raise AffectedBlueprintReadError(
            f"{context} must be a canonical sha256 fingerprint"
        )
    return value


def _impact_ids(value: Any, *, context: str) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)):
        raise AffectedBlueprintReadError(f"{context} must be an array")
    result = tuple(str(item).strip() for item in value)
    if any(not item for item in result):
        raise AffectedBlueprintReadError(f"{context} contains an empty id")
    if result != tuple(sorted(set(result))):
        raise AffectedBlueprintReadError(
            f"{context} must be sorted and duplicate-free"
        )
    return result


def _wire_id_array(value: Any, context: str) -> list[Any]:
    """Require JSON-array input at the machine-wire boundary.

    In-memory callers may use tuples while constructing a receipt, but a
    decoded receipt must not silently accept scalar strings, mappings, or
    other iterable look-alikes.  Keeping this check separate from
    ``_impact_ids`` lets the dataclass remain convenient without weakening
    current-schema deserialization.
    """

    if not isinstance(value, list):
        raise AffectedBlueprintReadError(f"{context} must be a JSON array")
    return value


def _impact_paths(value: Any, *, context: str) -> tuple[str, ...]:
    values = _impact_ids(value, context=context)
    normalized: list[str] = []
    for item in values:
        candidate = PurePosixPath(item.replace("\\", "/"))
        if candidate.is_absolute() or ".." in candidate.parts:
            raise AffectedBlueprintReadError(
                f"{context} must contain repository-relative paths"
            )
        normalized.append(candidate.as_posix())
    result = tuple(sorted(set(normalized)))
    if result != values:
        raise AffectedBlueprintReadError(
            f"{context} must use normalized repository-relative paths"
        )
    return result


@dataclass(frozen=True)
class AffectedImpactOwner:
    """One exact owner row in a current affected-impact plan."""

    owner_id: str
    disposition: str
    model_obligation_ids: tuple[str, ...] = ()
    test_owner_ids: tuple[str, ...] = ()
    evidence_owner_ids: tuple[str, ...] = ()
    required_parent_owner_ids: tuple[str, ...] = ()
    required_sibling_owner_ids: tuple[str, ...] = ()
    owner_identity: str = ""
    receipt_id: str = ""
    receipt_fingerprint: str = ""

    def __post_init__(self) -> None:
        owner_id = str(self.owner_id).strip()
        if not owner_id:
            raise AffectedBlueprintReadError("affected owner id is required")
        object.__setattr__(self, "owner_id", owner_id)
        disposition = str(self.disposition).strip()
        if disposition not in AFFECTED_IMPACT_OWNER_DISPOSITIONS:
            raise AffectedBlueprintReadError(
                f"unsupported affected owner disposition: {disposition}"
            )
        object.__setattr__(self, "disposition", disposition)
        for field_name in (
            "model_obligation_ids",
            "test_owner_ids",
            "evidence_owner_ids",
            "required_parent_owner_ids",
            "required_sibling_owner_ids",
        ):
            values = _impact_ids(
                getattr(self, field_name),
                context=f"affected owner {owner_id} {field_name}",
            )
            object.__setattr__(self, field_name, values)
        owner_identity = str(self.owner_identity).strip()
        if owner_identity and not re.fullmatch(r"sha256:[0-9a-f]{64}", owner_identity):
            raise AffectedBlueprintReadError(
                f"affected owner {owner_id} owner_identity must be a canonical sha256 fingerprint"
            )
        object.__setattr__(self, "owner_identity", owner_identity)
        receipt_id = str(self.receipt_id).strip()
        if receipt_id and any(character.isspace() for character in receipt_id):
            raise AffectedBlueprintReadError(
                f"affected owner {owner_id} receipt id must not contain whitespace"
            )
        object.__setattr__(self, "receipt_id", receipt_id)
        receipt_fingerprint = str(self.receipt_fingerprint).strip()
        if receipt_fingerprint:
            _impact_sha256(
                receipt_fingerprint,
                context=f"affected owner {owner_id} receipt fingerprint",
            )
        if disposition == "reuse_current" and (
            not self.receipt_id or not receipt_fingerprint
        ):
            raise AffectedBlueprintReadError(
                f"affected owner {owner_id} reuse_current requires an exact receipt"
            )
        if disposition != "reuse_current" and (self.receipt_id or receipt_fingerprint):
            raise AffectedBlueprintReadError(
                f"affected owner {owner_id} non-reuse disposition cannot carry a receipt"
            )
        object.__setattr__(self, "receipt_fingerprint", receipt_fingerprint)

    def to_dict(self) -> dict[str, Any]:
        return {
            "owner_id": self.owner_id,
            "disposition": self.disposition,
            "model_obligation_ids": list(self.model_obligation_ids),
            "test_owner_ids": list(self.test_owner_ids),
            "evidence_owner_ids": list(self.evidence_owner_ids),
            "required_parent_owner_ids": list(self.required_parent_owner_ids),
            "required_sibling_owner_ids": list(self.required_sibling_owner_ids),
            "owner_identity": self.owner_identity,
            "receipt_id": self.receipt_id,
            "receipt_fingerprint": self.receipt_fingerprint,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "AffectedImpactOwner":
        if not isinstance(value, Mapping):
            raise AffectedBlueprintReadError("affected impact owner must be an object")
        required = {
            "owner_id",
            "disposition",
            "model_obligation_ids",
            "test_owner_ids",
            "evidence_owner_ids",
            "required_parent_owner_ids",
            "required_sibling_owner_ids",
            "owner_identity",
            "receipt_id",
            "receipt_fingerprint",
        }
        if set(value) != required:
            raise AffectedBlueprintReadError(
                "affected impact owner fields are not current: "
                + repr(sorted(set(value) ^ required))
            )
        return cls(
            owner_id=value["owner_id"],
            disposition=value["disposition"],
            model_obligation_ids=tuple(_wire_id_array(value["model_obligation_ids"], "affected owner model_obligation_ids")),
            test_owner_ids=tuple(_wire_id_array(value["test_owner_ids"], "affected owner test_owner_ids")),
            evidence_owner_ids=tuple(_wire_id_array(value["evidence_owner_ids"], "affected owner evidence_owner_ids")),
            required_parent_owner_ids=tuple(_wire_id_array(value["required_parent_owner_ids"], "affected owner required_parent_owner_ids")),
            required_sibling_owner_ids=tuple(_wire_id_array(value["required_sibling_owner_ids"], "affected owner required_sibling_owner_ids")),
            owner_identity=value["owner_identity"],
            receipt_id=value["receipt_id"],
            receipt_fingerprint=value["receipt_fingerprint"],
        )


@dataclass(frozen=True)
class AffectedImpactPlan:
    """Current-only machine receipt for one bounded affected execution.

    The plan is intentionally independent from the full validation parent.  It
    names the changed boundary, its exact direct owners, and only the explicit
    parent/sibling edges that extend the closure.  A consumer may execute or
    reuse the listed owners, but it cannot invent owners from ``--member`` or
    widen the closure to all siblings.
    """

    changed_paths: tuple[str, ...]
    changed_components: tuple[tuple[str, str], ...]
    affected_member_ids: tuple[str, ...]
    affected_model_obligation_ids: tuple[str, ...]
    affected_test_owner_ids: tuple[str, ...]
    affected_evidence_owner_ids: tuple[str, ...]
    required_parent_dependencies: tuple[str, ...]
    required_sibling_dependencies: tuple[str, ...]
    unknown_impact_blockers: tuple[str, ...]
    source_fingerprint: str
    model_fingerprint: str
    test_fingerprint: str
    owner_fingerprint: str
    owner_rows: tuple[AffectedImpactOwner, ...]
    status: str = "pass"
    claim_boundary: str = (
        "This receipt proves one exact current affected closure only. It does not "
        "prove the whole model, release, or whole-system validation claim."
    )
    schema_version: str = AFFECTED_IMPACT_PLAN_SCHEMA

    def __post_init__(self) -> None:
        if self.schema_version != AFFECTED_IMPACT_PLAN_SCHEMA:
            raise AffectedBlueprintReadError(
                "affected impact plan schema is not current"
            )
        if self.status not in {"pass", "blocked", "invalid"}:
            raise AffectedBlueprintReadError(
                f"unsupported affected impact plan status: {self.status}"
            )
        object.__setattr__(
            self,
            "changed_paths",
            _impact_paths(self.changed_paths, context="affected changed paths"),
        )
        try:
            components = tuple(
                (str(component_id).strip(), str(fingerprint).strip())
                for component_id, fingerprint in self.changed_components
            )
        except (TypeError, ValueError) as exc:
            raise AffectedBlueprintReadError(
                "affected changed components must contain component/fingerprint pairs"
            ) from exc
        if components != tuple(sorted(components)):
            raise AffectedBlueprintReadError(
                "affected changed components must be sorted by component id"
            )
        if (not components and self.status == "pass") or len({item[0] for item in components}) != len(components):
            raise AffectedBlueprintReadError(
                "affected changed components must be unique and non-empty"
            )
        for component_id, fingerprint in components:
            if not component_id:
                raise AffectedBlueprintReadError(
                    "affected component id must be non-empty"
                )
            _impact_sha256(fingerprint, context=f"affected component {component_id}")
        object.__setattr__(self, "changed_components", components)
        for field_name in (
            "affected_member_ids",
            "affected_model_obligation_ids",
            "affected_test_owner_ids",
            "affected_evidence_owner_ids",
            "required_parent_dependencies",
            "required_sibling_dependencies",
            "unknown_impact_blockers",
        ):
            object.__setattr__(
                self,
                field_name,
                _impact_ids(
                    getattr(self, field_name),
                    context=f"affected impact plan {field_name}",
                ),
            )
        for field_name in (
            "source_fingerprint",
            "model_fingerprint",
            "test_fingerprint",
            "owner_fingerprint",
        ):
            _impact_sha256(
                str(getattr(self, field_name)),
                context=f"affected impact plan {field_name}",
            )
            object.__setattr__(self, field_name, str(getattr(self, field_name)))
        rows = tuple(self.owner_rows)
        if rows != tuple(sorted(rows, key=lambda item: item.owner_id)):
            raise AffectedBlueprintReadError(
                "affected impact owner rows must be sorted by owner id"
            )
        if len({item.owner_id for item in rows}) != len(rows):
            raise AffectedBlueprintReadError(
                "affected impact owner rows must have unique owner ids"
            )
        row_ids = tuple(item.owner_id for item in rows)
        if row_ids != self.affected_member_ids:
            raise AffectedBlueprintReadError(
                "affected member ids must exactly match affected owner rows"
            )
        if self.unknown_impact_blockers and self.status == "pass":
            raise AffectedBlueprintReadError(
                "unknown impact blockers cannot be hidden by a passing plan"
            )
        if not self.unknown_impact_blockers and self.status == "blocked":
            raise AffectedBlueprintReadError(
                "blocked affected impact plan must name an unknown-impact blocker"
            )
        object.__setattr__(self, "owner_rows", rows)
        object.__setattr__(self, "claim_boundary", str(self.claim_boundary).strip())

    @property
    def ok(self) -> bool:
        return self.status == "pass" and not self.unknown_impact_blockers

    @property
    def fingerprint(self) -> str:
        return fingerprint_value(self.to_dict(include_fingerprint=False))

    def to_dict(self, *, include_fingerprint: bool = True) -> dict[str, Any]:
        payload = {
            "schema_version": self.schema_version,
            "status": self.status,
            "ok": self.ok,
            "changed_paths": list(self.changed_paths),
            "changed_components": [
                {"component_id": component_id, "fingerprint": fingerprint}
                for component_id, fingerprint in self.changed_components
            ],
            "affected_member_ids": list(self.affected_member_ids),
            "affected_model_obligation_ids": list(self.affected_model_obligation_ids),
            "affected_test_owner_ids": list(self.affected_test_owner_ids),
            "affected_evidence_owner_ids": list(self.affected_evidence_owner_ids),
            "required_parent_dependencies": list(self.required_parent_dependencies),
            "required_sibling_dependencies": list(self.required_sibling_dependencies),
            "unknown_impact_blockers": list(self.unknown_impact_blockers),
            "source_fingerprint": self.source_fingerprint,
            "model_fingerprint": self.model_fingerprint,
            "test_fingerprint": self.test_fingerprint,
            "owner_fingerprint": self.owner_fingerprint,
            "owner_rows": [item.to_dict() for item in self.owner_rows],
            "claim_boundary": self.claim_boundary,
        }
        if include_fingerprint:
            payload["fingerprint"] = self.fingerprint
        return payload

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "AffectedImpactPlan":
        if not isinstance(value, Mapping):
            raise AffectedBlueprintReadError("affected impact plan must be an object")
        required = {
            "schema_version",
            "status",
            "ok",
            "changed_paths",
            "changed_components",
            "affected_member_ids",
            "affected_model_obligation_ids",
            "affected_test_owner_ids",
            "affected_evidence_owner_ids",
            "required_parent_dependencies",
            "required_sibling_dependencies",
            "unknown_impact_blockers",
            "source_fingerprint",
            "model_fingerprint",
            "test_fingerprint",
            "owner_fingerprint",
            "owner_rows",
            "claim_boundary",
            "fingerprint",
        }
        if set(value) != required:
            raise AffectedBlueprintReadError(
                "affected impact plan fields are not current: "
                + repr(sorted(set(value) ^ required))
            )
        if not isinstance(value["changed_paths"], list):
            raise AffectedBlueprintReadError(
                "affected changed paths must be a JSON array"
            )
        if not isinstance(value["changed_components"], list):
            raise AffectedBlueprintReadError(
                "affected changed components must be a JSON array"
            )
        if not isinstance(value["owner_rows"], list):
            raise AffectedBlueprintReadError(
                "affected owner rows must be a JSON array"
            )
        components = []
        for item in value["changed_components"]:
            if not isinstance(item, Mapping) or set(item) != {"component_id", "fingerprint"}:
                raise AffectedBlueprintReadError(
                    "affected changed component fields are not current"
                )
            components.append((item["component_id"], item["fingerprint"]))
        plan = cls(
            changed_paths=tuple(value["changed_paths"]),
            changed_components=tuple(components),
            affected_member_ids=tuple(_wire_id_array(value["affected_member_ids"], "affected member ids")),
            affected_model_obligation_ids=tuple(_wire_id_array(value["affected_model_obligation_ids"], "affected model obligation ids")),
            affected_test_owner_ids=tuple(_wire_id_array(value["affected_test_owner_ids"], "affected test owner ids")),
            affected_evidence_owner_ids=tuple(_wire_id_array(value["affected_evidence_owner_ids"], "affected evidence owner ids")),
            required_parent_dependencies=tuple(_wire_id_array(value["required_parent_dependencies"], "affected parent dependencies")),
            required_sibling_dependencies=tuple(_wire_id_array(value["required_sibling_dependencies"], "affected sibling dependencies")),
            unknown_impact_blockers=tuple(_wire_id_array(value["unknown_impact_blockers"], "affected impact blockers")),
            source_fingerprint=value["source_fingerprint"],
            model_fingerprint=value["model_fingerprint"],
            test_fingerprint=value["test_fingerprint"],
            owner_fingerprint=value["owner_fingerprint"],
            owner_rows=tuple(AffectedImpactOwner.from_dict(item) for item in value["owner_rows"]),
            status=value["status"],
            claim_boundary=value["claim_boundary"],
            schema_version=value["schema_version"],
        )
        if not isinstance(value["ok"], bool):
            raise AffectedBlueprintReadError(
                "affected impact plan ok must be a boolean"
            )
        supplied_fingerprint = str(value["fingerprint"])
        if supplied_fingerprint != plan.fingerprint:
            raise AffectedBlueprintReadError(
                "affected impact plan fingerprint mismatch"
            )
        if bool(value["ok"]) != plan.ok:
            raise AffectedBlueprintReadError(
                "affected impact plan ok flag is not derived from status"
            )
        return plan


ShardLoader = Callable[[str], Any]
ObjectLoader = Callable[[str], Any]


_MISSING = object()


def _field(value: Any, name: str, default: Any = _MISSING) -> Any:
    if isinstance(value, Mapping):
        if name in value:
            return value[name]
    else:
        namespace = getattr(value, "__dict__", None)
        if isinstance(namespace, dict) and name in namespace:
            return namespace[name]
        try:
            return object.__getattribute__(value, name)
        except AttributeError:
            pass
    if default is _MISSING:
        raise AffectedBlueprintReadError(f"normalized index omits {name}")
    return default


def _strict_object(
    value: Any,
    *,
    required: frozenset[str],
    optional: frozenset[str] = frozenset(),
    context: str,
) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise AffectedBlueprintReadError(f"{context} must be an object")
    payload = {str(key): item for key, item in value.items()}
    actual = set(payload)
    missing = sorted(required - actual)
    unknown = sorted(actual - required - optional)
    if missing or unknown:
        raise AffectedBlueprintReadError(
            f"{context} fields are not current: missing={missing}, unknown={unknown}"
        )
    return payload


def _string(value: Any, *, context: str) -> str:
    if not isinstance(value, str) or not value:
        raise AffectedBlueprintReadError(f"{context} must be a non-empty string")
    return value


def _string_array(value: Any, *, context: str) -> tuple[str, ...]:
    if not isinstance(value, Sequence) or isinstance(
        value, (str, bytes, bytearray)
    ):
        raise AffectedBlueprintReadError(f"{context} must be a JSON array")
    rows = tuple(
        _string(item, context=f"{context} member") for item in value
    )
    if len(rows) != len(set(rows)):
        raise AffectedBlueprintReadError(f"{context} contains duplicate ids")
    return rows


def _array_like(value: Any, *, context: str) -> tuple[Any, ...]:
    if not isinstance(value, Sequence) or isinstance(
        value, (str, bytes, bytearray)
    ):
        raise AffectedBlueprintReadError(f"{context} must be a JSON array")
    return tuple(value)


def _string_map(value: Any, *, context: str) -> dict[str, str]:
    rows = _index_pairs(value, context=context)
    return {
        _string(key, context=f"{context} key"): _string(
            item, context=f"{context} value"
        )
        for key, item in rows.items()
    }


def _reference_shard(value: Any, *, shard_id: str) -> dict[str, Any]:
    """Require the one direct-current reference-only shard shape."""

    payload = _strict_object(
        value,
        required=frozenset(
            {
                "schema_version",
                "kind",
                "shard_id",
                "coverage_ids",
                "referenced_object_ids",
            }
        ),
        context=f"affected shard {shard_id}",
    )
    if (
        payload["schema_version"]
        != BEHAVIOR_COVERAGE_REFERENCE_SHARD_SCHEMA
        or payload["kind"] != BEHAVIOR_COVERAGE_REFERENCE_SHARD_KIND
    ):
        raise AffectedBlueprintReadError(
            f"affected shard schema is not current: {shard_id}"
        )
    if _string(payload["shard_id"], context="affected shard id") != shard_id:
        raise AffectedBlueprintReadError(
            f"affected shard identity mismatch: {shard_id}"
        )
    coverage_ids = _string_array(
        payload["coverage_ids"],
        context=f"affected shard coverage ids {shard_id}",
    )
    referenced_object_ids = _string_array(
        payload["referenced_object_ids"],
        context=f"affected shard referenced object ids {shard_id}",
    )
    if not coverage_ids or coverage_ids != tuple(sorted(coverage_ids)):
        raise AffectedBlueprintReadError(
            f"affected shard coverage ids are not sorted and non-empty: {shard_id}"
        )
    if referenced_object_ids != coverage_ids:
        raise AffectedBlueprintReadError(
            f"affected shard reference ids differ from coverage ids: {shard_id}"
        )
    return dict(payload)


_EXPLICIT_REFERENCE_KEYS = frozenset(
    {
        "referenced_object_ids",
        "object_ids",
        "shared_object_ids",
    }
)
_EXPLICIT_ANCESTOR_KEYS = frozenset(
    {
        "ancestor_ids",
        "ancestor_object_ids",
        "parent_object_ids",
        "required_ancestor_ids",
    }
)
_INFERRED_REFERENCE_KEYS = frozenset(
    {
        "behavior_block_id",
        "behavior_block_object_id",
        "case_id",
        "implementation_surface_id",
        "implementation_surface_object_id",
        "intent_id",
        "model_element_id",
        "model_obligation_id",
        "node_object_id",
        "oracle_id",
        "oracle_member_id",
        "owner_contract_id",
        "owner_id",
        "parent_object_id",
        "portable_binding_id",
        "receipt_id",
        "resource_id",
        "surface_object_id",
        "surface_record_id",
        "semantic_spec_id",
        "supporting_surface_id",
        "test_node_id",
        "topology_node_id",
    }
)
_INFERRED_REFERENCE_COLLECTION_KEYS = frozenset(
    {
        "intent_ids",
        "intent_contribution_ids",
        "oracle_ids",
        "portable_binding_ids",
        "relation_object_ids",
        "resource_ids",
        "semantic_spec_ids",
        "test_node_ids",
        "coverage_execution_evidence_ids",
    }
)
_INFERRED_ANCESTOR_KEYS = frozenset(
    {
        "behavior_block_id",
        "behavior_block_object_id",
        "implementation_surface_object_id",
        "model_element_id",
        "owner_contract_id",
        "owner_id",
        "parent_object_id",
        "surface_object_id",
        "surface_record_id",
        "topology_node_id",
    }
)


def _ids(value: Any) -> tuple[str, ...]:
    if isinstance(value, str):
        return (value,) if value else ()
    if isinstance(value, Sequence) and not isinstance(
        value, (str, bytes, bytearray)
    ):
        return tuple(str(item) for item in value if str(item))
    return ()


def _index_pairs(value: Any, *, context: str) -> dict[str, Any]:
    if isinstance(value, Mapping):
        rows = tuple(value.items())
    else:
        try:
            rows = tuple(value)
        except TypeError as exc:
            raise AffectedBlueprintReadError(f"{context} must be an iterable") from exc
    result: dict[str, Any] = {}
    for row in rows:
        if not isinstance(row, Sequence) or isinstance(
            row, (str, bytes, bytearray)
        ) or len(row) != 2:
            raise AffectedBlueprintReadError(
                f"{context} entries must be exact id/value pairs"
            )
        row_id = str(row[0])
        if not row_id:
            raise AffectedBlueprintReadError(f"{context} contains an empty id")
        if row_id in result:
            raise AffectedBlueprintReadError(
                f"{context} contains duplicate id: {row_id}"
            )
        result[row_id] = row[1]
    return result


def _discover_links(
    value: Any,
) -> tuple[set[str], set[str], set[str]]:
    """Return explicit refs, inferred refs, and ancestor refs.

    Explicit reference declarations are authoritative and must resolve. Inferred
    identifiers are only followed when the normalized object index knows them.
    """

    explicit: set[str] = set()
    inferred: set[str] = set()
    ancestors: set[str] = set()

    def visit(node: Any) -> None:
        if isinstance(node, Mapping):
            for raw_key, child in node.items():
                key = str(raw_key)
                if key in _EXPLICIT_REFERENCE_KEYS:
                    explicit.update(_ids(child))
                elif key in _EXPLICIT_ANCESTOR_KEYS:
                    found = set(_ids(child))
                    explicit.update(found)
                    ancestors.update(found)
                elif key in _INFERRED_REFERENCE_KEYS:
                    found = set(_ids(child))
                    inferred.update(found)
                    if key in _INFERRED_ANCESTOR_KEYS:
                        ancestors.update(found)
                elif key in _INFERRED_REFERENCE_COLLECTION_KEYS:
                    inferred.update(_ids(child))
                visit(child)
        elif isinstance(node, Sequence) and not isinstance(
            node, (str, bytes, bytearray)
        ):
            for child in node:
                visit(child)

    visit(value)
    return explicit, inferred, ancestors


@dataclass(frozen=True)
class AffectedTopologyInvalidationEdge:
    """One exact directed reason that expands an affected topology seed."""

    source_id: str
    target_id: str
    edge_kind: str
    evidence_object_ids: tuple[str, ...]
    via_node_id: str = ""

    def __post_init__(self) -> None:
        for name in ("source_id", "target_id"):
            object.__setattr__(
                self,
                name,
                _string(getattr(self, name), context=f"topology edge {name}"),
            )
        if self.source_id == self.target_id:
            raise AffectedBlueprintReadError(
                "topology invalidation edge cannot target its own source"
            )
        if self.edge_kind not in AFFECTED_TOPOLOGY_INVALIDATION_KINDS:
            raise AffectedBlueprintReadError(
                f"unknown topology invalidation edge kind: {self.edge_kind}"
            )
        evidence = tuple(
            sorted(
                _string_array(
                    self.evidence_object_ids,
                    context="topology invalidation evidence objects",
                )
            )
        )
        if not evidence:
            raise AffectedBlueprintReadError(
                "topology invalidation edge requires content-addressed evidence"
            )
        object.__setattr__(self, "evidence_object_ids", evidence)
        if self.via_node_id:
            object.__setattr__(
                self,
                "via_node_id",
                _string(
                    self.via_node_id,
                    context="topology invalidation via node",
                ),
            )
        if self.edge_kind == "sibling" and not self.via_node_id:
            raise AffectedBlueprintReadError(
                "sibling invalidation requires its exact common parent"
            )

    @property
    def schema_version(self) -> str:
        return AFFECTED_TOPOLOGY_INVALIDATION_EDGE_SCHEMA

    @property
    def identity(self) -> tuple[str, str, str, str]:
        return (
            self.source_id,
            self.target_id,
            self.edge_kind,
            self.via_node_id,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "source_id": self.source_id,
            "target_id": self.target_id,
            "edge_kind": self.edge_kind,
            "evidence_object_ids": list(self.evidence_object_ids),
            "via_node_id": self.via_node_id,
        }

    @classmethod
    def from_dict(cls, value: Any) -> "AffectedTopologyInvalidationEdge":
        payload = _strict_object(
            value,
            required=frozenset(
                {
                    "schema_version",
                    "source_id",
                    "target_id",
                    "edge_kind",
                    "evidence_object_ids",
                    "via_node_id",
                }
            ),
            context="affected topology invalidation edge",
        )
        if payload["schema_version"] != AFFECTED_TOPOLOGY_INVALIDATION_EDGE_SCHEMA:
            raise AffectedBlueprintReadError(
                "affected topology invalidation edge schema is not current"
            )
        via_node_id = payload["via_node_id"]
        if not isinstance(via_node_id, str):
            raise AffectedBlueprintReadError(
                "topology invalidation via node must be a string"
            )
        return cls(
            source_id=_string(payload["source_id"], context="topology edge source"),
            target_id=_string(payload["target_id"], context="topology edge target"),
            edge_kind=_string(payload["edge_kind"], context="topology edge kind"),
            evidence_object_ids=_string_array(
                payload["evidence_object_ids"],
                context="topology invalidation evidence objects",
            ),
            via_node_id=via_node_id,
        )


@dataclass(frozen=True)
class AffectedBlueprintIndex:
    """Content-addressed affected-read index over one qualified target ledger."""

    blueprint_fingerprint: str
    logical_fingerprint: str
    target_object_id: str
    ledger_row_ids: tuple[str, ...]
    object_fingerprints: tuple[tuple[str, str], ...]
    shard_fingerprints: tuple[tuple[str, str], ...]
    shard_member_ids: tuple[tuple[str, tuple[str, ...]], ...]
    affected_edges: tuple[tuple[str, tuple[str, ...]], ...]
    topology_invalidation_edges: tuple[AffectedTopologyInvalidationEdge, ...] = ()

    def __post_init__(self) -> None:
        for name in (
            "blueprint_fingerprint",
            "logical_fingerprint",
            "target_object_id",
        ):
            if not str(getattr(self, name, "")):
                raise AffectedBlueprintReadError(
                    f"affected blueprint index requires {name}"
                )
        object_rows = _index_pairs(
            self.object_fingerprints, context="object fingerprint index"
        )
        shard_rows = _index_pairs(
            self.shard_fingerprints, context="shard fingerprint index"
        )
        shard_members = _index_pairs(
            self.shard_member_ids, context="shard member index"
        )
        edges = _index_pairs(self.affected_edges, context="affected edge index")
        object_ids = frozenset(object_rows)
        shard_ids = frozenset(shard_rows)
        supplied_topology_edges = tuple(self.topology_invalidation_edges)
        if any(
            not isinstance(row, AffectedTopologyInvalidationEdge)
            for row in supplied_topology_edges
        ):
            raise AffectedBlueprintReadError(
                "topology invalidation edges require current typed records"
            )
        topology_edges = tuple(
            sorted(
                supplied_topology_edges,
                key=lambda row: (*row.identity, row.evidence_object_ids),
            )
        )
        topology_edge_ids = tuple(row.identity for row in topology_edges)
        if len(topology_edge_ids) != len(set(topology_edge_ids)):
            raise AffectedBlueprintReadError(
                "topology invalidation edge identity is duplicated"
            )
        object.__setattr__(self, "topology_invalidation_edges", topology_edges)
        if self.target_object_id not in object_rows:
            raise AffectedBlueprintReadError(
                "affected blueprint target object is not content-addressed"
            )
        if not self.ledger_row_ids:
            raise AffectedBlueprintReadError(
                "affected blueprint index requires ordered ledger rows"
            )
        if len(self.ledger_row_ids) != len(set(self.ledger_row_ids)):
            raise AffectedBlueprintReadError(
                "affected blueprint index contains duplicate ledger rows"
            )
        if any(not str(value) for value in object_rows.values()):
            raise AffectedBlueprintReadError(
                "affected blueprint object fingerprint index contains an empty value"
            )
        if any(not str(value) for value in shard_rows.values()):
            raise AffectedBlueprintReadError(
                "affected blueprint shard fingerprint index contains an empty value"
            )
        missing_rows = sorted(set(self.ledger_row_ids) - object_ids)
        if missing_rows:
            raise AffectedBlueprintReadError(
                "affected blueprint index has unaddressed ledger rows: "
                + ", ".join(missing_rows)
            )
        missing_shards = sorted(set(shard_members) - shard_ids)
        if missing_shards:
            raise AffectedBlueprintReadError(
                "affected blueprint shard members have no fingerprint: "
                + ", ".join(missing_shards)
            )
        for affected_id, referenced_ids in edges.items():
            if not affected_id:
                raise AffectedBlueprintReadError(
                    "affected blueprint edge contains an empty affected id"
                )
            refs = _ids(referenced_ids)
            missing = sorted(set(refs) - object_ids)
            if not refs or missing:
                raise AffectedBlueprintReadError(
                    "affected blueprint edge is incomplete for "
                    f"{affected_id}: missing={missing}"
                )
        known_affected_ids = {
            *edges,
            *object_ids,
            *(
                member_id
                for member_ids in shard_members.values()
                for member_id in _ids(member_ids)
            ),
        }
        for edge in topology_edges:
            unknown_endpoints = sorted(
                {edge.source_id, edge.target_id} - known_affected_ids
            )
            missing_evidence = sorted(
                set(edge.evidence_object_ids) - object_ids
            )
            if unknown_endpoints or missing_evidence:
                raise AffectedBlueprintReadError(
                    "topology invalidation edge is incomplete: "
                    f"unknown_endpoints={unknown_endpoints}, "
                    f"missing_evidence={missing_evidence}"
                )

    @property
    def schema_version(self) -> str:
        return AFFECTED_BLUEPRINT_INDEX_SCHEMA

    def identity_payload(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "blueprint_fingerprint": self.blueprint_fingerprint,
            "logical_fingerprint": self.logical_fingerprint,
            "target_object_id": self.target_object_id,
            "ledger_row_ids": list(self.ledger_row_ids),
            "object_fingerprints": dict(self.object_fingerprints),
            "shard_fingerprints": dict(self.shard_fingerprints),
            "shard_member_ids": {
                shard_id: list(member_ids)
                for shard_id, member_ids in self.shard_member_ids
            },
            "affected_edges": {
                affected_id: list(object_ids)
                for affected_id, object_ids in self.affected_edges
            },
            "topology_invalidation_edges": [
                row.to_dict() for row in self.topology_invalidation_edges
            ],
            "claim_boundary": (
                "This index selects one content-addressed affected closure and its "
                "qualified readiness ledger. It is not a whole-blueprint payload."
            ),
        }

    @cached_property
    def fingerprint(self) -> str:
        return fingerprint_value(self.identity_payload())

    def to_dict(self) -> dict[str, Any]:
        return {**self.identity_payload(), "fingerprint": self.fingerprint}

    @classmethod
    def from_dict(cls, value: Any) -> "AffectedBlueprintIndex":
        payload = _strict_object(
            value,
            required=frozenset(
                {
                    "schema_version",
                    "blueprint_fingerprint",
                    "logical_fingerprint",
                    "target_object_id",
                    "ledger_row_ids",
                    "object_fingerprints",
                    "shard_fingerprints",
                    "shard_member_ids",
                    "affected_edges",
                    "topology_invalidation_edges",
                    "claim_boundary",
                    "fingerprint",
                }
            ),
            context="affected blueprint index",
        )
        if payload["schema_version"] != AFFECTED_BLUEPRINT_INDEX_SCHEMA:
            raise AffectedBlueprintReadError(
                "affected blueprint index schema is not current"
            )
        _string(payload["claim_boundary"], context="affected index claim boundary")
        index = cls(
            blueprint_fingerprint=_string(
                payload["blueprint_fingerprint"],
                context="affected index blueprint fingerprint",
            ),
            logical_fingerprint=_string(
                payload["logical_fingerprint"],
                context="affected index logical fingerprint",
            ),
            target_object_id=_string(
                payload["target_object_id"],
                context="affected index target object id",
            ),
            ledger_row_ids=_string_array(
                payload["ledger_row_ids"], context="affected index ledger rows"
            ),
            object_fingerprints=tuple(
                sorted(
                    _string_map(
                        payload["object_fingerprints"],
                        context="object fingerprint index",
                    ).items()
                )
            ),
            shard_fingerprints=tuple(
                sorted(
                    _string_map(
                        payload["shard_fingerprints"],
                        context="shard fingerprint index",
                    ).items()
                )
            ),
            shard_member_ids=tuple(
                sorted(
                    (
                        _string(key, context="shard member index key"),
                        tuple(
                            sorted(
                                _string_array(
                                    item,
                                    context=f"shard member index {key}",
                                )
                            )
                        ),
                    )
                    for key, item in _index_pairs(
                        payload["shard_member_ids"],
                        context="shard member index",
                    ).items()
                )
            ),
            affected_edges=tuple(
                sorted(
                    (
                        _string(key, context="affected edge index key"),
                        tuple(
                            sorted(
                                _string_array(
                                    item,
                                    context=f"affected edge index {key}",
                                )
                            )
                        ),
                    )
                    for key, item in _index_pairs(
                        payload["affected_edges"],
                        context="affected edge index",
                    ).items()
                )
            ),
            topology_invalidation_edges=tuple(
                AffectedTopologyInvalidationEdge.from_dict(item)
                for item in _array_like(
                    payload["topology_invalidation_edges"],
                    context="topology invalidation edge array",
                )
            ),
        )
        if _string(
            payload["fingerprint"], context="affected index fingerprint"
        ) != index.fingerprint:
            raise AffectedBlueprintReadError(
                "affected blueprint index fingerprint mismatch"
            )
        return index


@dataclass(frozen=True)
class AffectedBlueprintProjectionBundle:
    """Selective, current-bound projection inputs for the affected reader.

    A canonical software projection contains many unrelated shards.  The
    affected CLI must be able to consume only the identity, affected index,
    reference shards, shared objects, and implementation inventory needed for
    one bounded closure.  This bundle deliberately exposes loader callables
    instead of a reconstructed whole ``CanonicalBlueprintProjection``.
    """

    projection_root: Path
    projection_fingerprint: str
    blueprint_fingerprint: str
    index: AffectedBlueprintIndex
    shard_payloads: tuple[tuple[str, Any], ...]
    object_payloads: tuple[tuple[str, Any], ...]
    identity: Mapping[str, Any]
    surface_catalog: Mapping[str, Any] | None
    accepted_snapshot: Mapping[str, Any]
    authority_snapshot_fingerprint: str
    authority_head_fingerprint: str
    unknown_entries: tuple[str, ...] = ()
    object_ids: tuple[str, ...] = ()
    # Canonical disk projections use offset locators.  In-memory fixtures and
    # older callers continue to use the tuple payload fallback above.
    object_locator: _JsonArrayRowLocator | None = None
    shard_locator: _JsonArrayRowLocator | None = None
    # The native loader result is invocation-local and is never serialized.
    # Passing it through the projection bundle prevents the task-context
    # projection from resolving the same authority identity a second time.
    authority_state: Any | None = None

    def close(self) -> None:
        """Release invocation-local selective lookup resources.

        Affected reads may consume both locators while traversing one closure.
        Keep their lifetime at the bundle/request boundary so callers do not
        reopen a store for each seed id, and make cleanup explicit on both
        success and failure paths.
        """

        for locator in (self.shard_locator, self.object_locator):
            if locator is not None:
                locator.close()

    def load_shard(self, shard_id: str) -> Any:
        key = str(shard_id)
        if self.shard_locator is not None:
            try:
                payload = self.shard_locator.load(key)
            except KeyError as exc:
                raise KeyError(key) from exc
            expected = dict(self.index.shard_fingerprints).get(key)
            if expected is None or fingerprint_value(payload) != expected:
                raise AffectedBlueprintReadError(
                    f"projection_identity_mismatch: behavior shard fingerprint mismatch: {key}"
                )
            return payload
        values = dict(self.shard_payloads)
        try:
            return values[key]
        except KeyError as exc:
            raise KeyError(key) from exc

    def load_object(self, object_id: str) -> Any:
        key = str(object_id)
        if self.object_locator is not None:
            try:
                value = self.object_locator.load(key)
            except KeyError as exc:
                raise KeyError(key) from exc
            expected = dict(self.index.object_fingerprints).get(key)
            if expected is None:
                raise AffectedBlueprintReadError(
                    f"projection_lookup_missing: object fingerprint is not indexed: {key}"
                )
            if fingerprint_value(value) != expected:
                raise AffectedBlueprintReadError(
                    f"projection_identity_mismatch: shared object fingerprint mismatch: {key}"
                )
            return value
        values = dict(self.object_payloads)
        try:
            value = values[key]
        except KeyError as exc:
            raise KeyError(str(object_id)) from exc
        expected = dict(self.index.object_fingerprints).get(key)
        if expected is None:
            raise AffectedBlueprintReadError(
                f"projection_lookup_missing: object fingerprint is not indexed: {key}"
            )
        if fingerprint_value(value) != expected:
            raise AffectedBlueprintReadError(
                f"projection_identity_mismatch: shared object fingerprint mismatch: {key}"
            )
        return value

    def changed_path_candidates(self, changed_paths: Iterable[str]) -> tuple[tuple[str, ...], tuple[str, ...]]:
        """Resolve changed paths to exact registered seeds without guessing.

        The first tuple contains unique seed ids when every supplied path has
        exactly one match.  The second tuple contains normalized paths with no
        match.  Multiple matches raise a typed reader error so a caller cannot
        silently choose one owner.
        """

        rows = _projection_surface_rows(self.surface_catalog)
        by_path: dict[str, list[str]] = {}
        for row in rows:
            surface_id = str(
                row.get("surface_id", row.get("implementation_surface_id", ""))
            ).strip()
            path = str(row.get("path", "") or "").replace("\\", "/")
            if not surface_id or not path:
                continue
            candidate = PurePosixPath(path)
            if candidate.is_absolute() or ".." in candidate.parts:
                continue
            by_path.setdefault(candidate.as_posix(), []).append(surface_id)

        known_ids = {
            *(object_id for object_id, _fingerprint in self.index.object_fingerprints),
            *(member_id for _shard_id, members in self.index.shard_member_ids for member_id in members),
            *(affected_id for affected_id, _object_ids in self.index.affected_edges),
        }
        selected: set[str] = set()
        unknown: list[str] = []
        for raw_path in changed_paths:
            raw = str(raw_path).strip()
            candidate = PurePosixPath(raw.replace("\\", "/"))
            if not raw or candidate.is_absolute() or ".." in candidate.parts:
                raise AffectedBlueprintReadError(
                    f"invalid_changed_path: {raw_path}"
                )
            normalized = candidate.as_posix()
            matches = sorted(set(by_path.get(normalized, ())))
            if len(matches) > 1:
                raise AffectedBlueprintReadError(
                    "owner_ambiguous: changed path "
                    f"{normalized} maps to {', '.join(matches)}"
                )
            if not matches:
                unknown.append(normalized)
                continue
            seed = matches[0]
            if seed not in known_ids:
                unknown.append(normalized)
                continue
            selected.add(seed)
        return tuple(sorted(selected)), tuple(sorted(set(unknown)))


# Publicly readable alias for callers that describe the artifact as a
# projection rather than a bundle.  Keep one implementation and one identity.
AffectedBlueprintProjection = AffectedBlueprintProjectionBundle


def _projection_json_load(path: Path, *, context: str) -> Any:
    try:
        raw = path.read_text(encoding="utf-8")

        def reject_duplicate(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
            result: dict[str, Any] = {}
            for key, value in pairs:
                if key in result:
                    raise ValueError(f"duplicate JSON key: {key}")
                result[str(key)] = value
            return result

        value = json.loads(
            raw,
            object_pairs_hook=reject_duplicate,
            parse_constant=lambda item: (_ for _ in ()).throw(
                ValueError(f"non-finite JSON number: {item}")
            ),
        )
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        raise AffectedBlueprintReadError(
            f"projection_read_error: cannot load {context}: {exc}"
        ) from exc
    if not isinstance(value, Mapping):
        raise AffectedBlueprintReadError(f"projection_read_error: {context} must be a JSON object")
    return value


def _projection_is_reparse(value: os.stat_result) -> bool:
    flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    return stat.S_ISLNK(value.st_mode) or bool(getattr(value, "st_file_attributes", 0) & flag)


def _projection_relative_path(value: Any, *, context: str) -> str:
    raw = str(value or "").strip().replace("\\", "/")
    candidate = PurePosixPath(raw)
    if (
        not raw
        or candidate.is_absolute()
        or ".." in candidate.parts
        or not candidate.parts
        or ":" in candidate.parts[0]
        or raw.startswith(("/", "//"))
        or candidate.as_posix() != raw
    ):
        raise AffectedBlueprintReadError(
            f"projection_path_traversal: {context} escapes projection root"
        )
    return candidate.as_posix()


def _projection_file(root: Path, relative: str, *, context: str) -> Path:
    candidate = root.joinpath(*PurePosixPath(relative).parts)
    try:
        root_stat = os.lstat(root)
        candidate_stat = os.lstat(candidate)
    except OSError as exc:
        raise AffectedBlueprintReadError(
            f"projection_read_error: cannot inspect {context}: {exc}"
        ) from exc
    if _projection_is_reparse(root_stat) or not stat.S_ISDIR(root_stat.st_mode):
        raise AffectedBlueprintReadError(
            "projection_path_traversal: projection root must be a real directory"
        )
    current = root
    for part in PurePosixPath(relative).parts[:-1]:
        current = current / part
        try:
            current_stat = os.lstat(current)
        except OSError as exc:
            raise AffectedBlueprintReadError(
                f"projection_read_error: cannot inspect {context}: {exc}"
            ) from exc
        if _projection_is_reparse(current_stat) or not stat.S_ISDIR(current_stat.st_mode):
            raise AffectedBlueprintReadError(
                f"projection_path_traversal: {context} contains an unsafe parent"
            )
    if _projection_is_reparse(candidate_stat) or not stat.S_ISREG(candidate_stat.st_mode):
        raise AffectedBlueprintReadError(
            f"projection_path_traversal: {context} is not a regular file"
        )
    return candidate


def _projection_surface_rows(value: Mapping[str, Any] | None) -> tuple[Mapping[str, Any], ...]:
    if not isinstance(value, Mapping):
        return ()
    rows = value.get("surfaces", value.get("implementation_surfaces", ()))
    if not isinstance(rows, (list, tuple)):
        return ()
    return tuple(row for row in rows if isinstance(row, Mapping))


def _projection_authority_snapshot(root: Path) -> tuple[Any, Mapping[str, Any]]:
    try:
        from .model_authority_store import load_current_model_authority_state

        state = load_current_model_authority_state(root)
    except Exception as exc:
        raise AffectedBlueprintReadError(
            f"accepted_snapshot_unavailable: current model authority is not usable: {exc}"
        ) from exc
    snapshot_id = str(state.snapshot.fingerprint)
    subject_revision = str(state.snapshot.subject_revision)
    head_fingerprint = str(state.head.fingerprint)
    revision_set = str(getattr(state.head, "accepted_revision_set_fingerprint", ""))
    accepted = {
        "as_of": subject_revision,
        "snapshot_id": snapshot_id,
        "snapshot_fingerprint": snapshot_id,
        "authority_head_fingerprint": head_fingerprint,
        "accepted_revision_set_fingerprint": revision_set,
        "claim_boundary": "Current model authority snapshot resolved from project authority.",
    }
    return state, accepted


def _projection_identity_value(identity: Mapping[str, Any], *names: str) -> str:
    for name in names:
        value = identity.get(name)
        if value not in (None, ""):
            return str(value)
    return ""


def _projection_lookup_cache_path(
    projection_root: Path,
    authority_root: str | Path,
    projection_fingerprint: str,
) -> Path:
    """Return the bounded cache lane used by canonical projection writers."""

    anchors = [projection_root.parent.resolve(), Path(authority_root).resolve()]
    candidates: list[Path] = []
    for anchor in anchors:
        for candidate in (anchor, *anchor.parents):
            if candidate == Path(candidate.anchor):
                continue
            cache = (
                candidate
                / "work"
                / "flowguard"
                / "canonical-blueprint"
                / "lookup-cache"
                / f"{projection_fingerprint.removeprefix('sha256:')}.json"
            )
            if cache not in candidates:
                candidates.append(cache)
    for candidate in candidates:
        if candidate.is_file() and not candidate.is_symlink():
            return candidate
    # Prefer the projection's nearest project-owned lane for the typed
    # missing-cache diagnostic.  No fallback to another generation is allowed.
    return candidates[0]


def _load_projection_lookup_cache(
    projection_root: Path,
    authority_root: str | Path,
    *,
    projection_fingerprint: str,
    rows_by_kind: Mapping[str, Mapping[str, Any]],
    index: AffectedBlueprintIndex,
) -> tuple[_JsonArrayRowLocator, _JsonArrayRowLocator, Path]:
    """Load and bind the writer-produced offset cache without trusting it."""

    path = _projection_lookup_cache_path(
        projection_root, authority_root, projection_fingerprint
    )
    if not path.is_file() or path.is_symlink():
        raise AffectedBlueprintReadError(
            "projection_lookup_missing: canonical projection lookup cache is "
            f"missing: {path}"
        )
    payload = _projection_json_load(path, context="projection lookup cache")
    required = {"schema_version", "projection_fingerprint", "containers"}
    if set(payload) != required or payload.get("schema_version") != "flowguard.projection_lookup_cache.v1":
        raise AffectedBlueprintReadError(
            "projection_schema_invalid: projection lookup cache is not current"
        )
    if payload.get("projection_fingerprint") != projection_fingerprint:
        raise AffectedBlueprintReadError(
            "projection_identity_mismatch: projection lookup cache belongs to another projection"
        )
    containers = payload.get("containers")
    if not isinstance(containers, Mapping) or set(containers) != {
        "behavior_shards",
        "shared_objects",
    }:
        raise AffectedBlueprintReadError(
            "projection_schema_invalid: projection lookup cache containers are not exact-current"
        )

    locators: list[_JsonArrayRowLocator] = []
    metadata_keys = (
        "shard_id",
        "kind",
        "relative_path",
        "member_ids",
        "content_fingerprint",
    )
    try:
        for kind, row_key, value_key, exact_fields, expected_ids in (
            (
                "behavior_shards",
                "shard_id",
                None,
                False,
                set(dict(index.shard_fingerprints)),
            ),
            (
                "shared_objects",
                "object_id",
                "value",
                True,
                set(dict(index.object_fingerprints)),
            ),
        ):
            item = containers.get(kind)
            if not isinstance(item, Mapping) or set(item) != {
                "relative_path",
                "content_fingerprint",
                "rows",
            }:
                raise AffectedBlueprintReadError(
                    f"projection_schema_invalid: {kind} lookup cache row is not exact-current"
                )
            manifest_row = rows_by_kind[kind]
            if (
                item["relative_path"] != manifest_row["relative_path"]
                or item["content_fingerprint"] != manifest_row["content_fingerprint"]
            ):
                raise AffectedBlueprintReadError(
                    f"projection_identity_mismatch: {kind} lookup cache is bound to another shard"
                )
            raw_rows = item["rows"]
            if not isinstance(raw_rows, Mapping) or set(raw_rows) != expected_ids:
                raise AffectedBlueprintReadError(
                    f"projection_identity_mismatch: {kind} lookup cache row set disagrees with accepted index"
                )
            relative = _projection_relative_path(
                item["relative_path"], context=f"{kind} lookup shard"
            )
            shard_path = _projection_file(
                projection_root, relative, context=f"{kind} lookup shard"
            )
            offsets: dict[str, tuple[int, int]] = {}
            for row_id, raw_offset in raw_rows.items():
                if not isinstance(row_id, str) or not isinstance(raw_offset, list) or len(raw_offset) != 2:
                    raise AffectedBlueprintReadError(
                        f"projection_schema_invalid: {kind} lookup offset is not a pair"
                    )
                start, length = raw_offset
                if not isinstance(start, int) or not isinstance(length, int):
                    raise AffectedBlueprintReadError(
                        f"projection_schema_invalid: {kind} lookup offset is not integral"
                    )
                try:
                    size = shard_path.stat().st_size
                except OSError as exc:
                    raise AffectedBlueprintReadError(
                        f"projection_read_error: cannot stat {kind} lookup shard: {exc}"
                    ) from exc
                if start < 0 or length <= 0 or start + length > size:
                    raise AffectedBlueprintReadError(
                        f"projection_identity_mismatch: {kind} lookup offset is outside its shard"
                    )
                offsets[row_id] = (start, start + length)
            locator = _JsonArrayRowLocator(
                _projection_file(projection_root, relative, context=f"{kind} shard"),
                f"{kind} shard",
                row_key=row_key,
                value_key=value_key,
                exact_row_fields=exact_fields,
                preindexed_offsets=offsets,
            )
            # Bind envelope metadata, accepted content identity, and offset
            # bounds before returning a locator to the affected reader.
            shard_keys = {
                "schema_version",
                "shard_id",
                "kind",
                "relative_path",
                "member_ids",
                "payload",
                "content_fingerprint",
            }
            if set(locator.field_names()) != shard_keys:
                raise AffectedBlueprintReadError(
                    f"projection_schema_invalid: {kind} shard is not exact-current"
                )
            for metadata_key in metadata_keys:
                if locator.load_field(metadata_key) != manifest_row[metadata_key]:
                    raise AffectedBlueprintReadError(
                        f"projection_identity_mismatch: {kind} shard metadata disagrees with manifest"
                    )
            # The index is intentionally a warm lookup surface.  Do not hash the
            # complete payload while opening it; the selected row's canonical
            # content fingerprint is verified at the point where that row is
            # materialized below.  This keeps a warm read proportional to the
            # requested member instead of falling back to a full-shard scan.
            if locator.row_keys() != tuple(sorted(expected_ids)):
                raise AffectedBlueprintReadError(
                    f"projection_identity_mismatch: {kind} lookup cache is not deterministic"
                )
            locators.append(locator)
        return locators[0], locators[1], path
    except Exception:
        for locator in locators:
            locator.close()
        raise


def load_affected_blueprint_projection(
    projection_root: str | Path,
    *,
    authority_root: str | Path,
    accepted_snapshot: Mapping[str, Any] | None = None,
) -> AffectedBlueprintProjectionBundle:
    """Load only the canonical shards required by an affected read.

    This is intentionally not an adapter around
    ``load_canonical_blueprint_projection``: that loader materializes every
    shard and verifies the full tree.  The affected route reads the manifest,
    five selected kinds, and the exact authority identity, then leaves closure
    traversal to :class:`AffectedBlueprintReader`.
    """

    root = Path(projection_root)
    try:
        root_stat = os.lstat(root)
    except OSError as exc:
        raise AffectedBlueprintReadError(
            f"projection_root_required: cannot inspect projection root: {exc}"
        ) from exc
    if _projection_is_reparse(root_stat) or not stat.S_ISDIR(root_stat.st_mode):
        raise AffectedBlueprintReadError(
            "projection_path_traversal: projection root must be a real directory"
        )

    manifest = _projection_json_load(
        _projection_file(root, "manifest.json", context="projection manifest"),
        context="projection manifest",
    )
    required_manifest_keys = {
        "schema_version",
        "blueprint_fingerprint",
        "shards",
        "projection_fingerprint",
    }
    if set(manifest) != required_manifest_keys or manifest.get("schema_version") != "1.2":
        raise AffectedBlueprintReadError(
            "projection_schema_invalid: canonical projection manifest is not current"
        )
    rows = manifest.get("shards")
    if not isinstance(rows, list):
        raise AffectedBlueprintReadError("projection_schema_invalid: shard manifest is not an array")
    manifest_without_fingerprint = {
        key: manifest[key] for key in required_manifest_keys if key != "projection_fingerprint"
    }
    if str(manifest["projection_fingerprint"]) != fingerprint_value(manifest_without_fingerprint):
        raise AffectedBlueprintReadError("projection_identity_mismatch: projection fingerprint is stale")

    row_keys = {
        "shard_id",
        "kind",
        "relative_path",
        "member_ids",
        "content_fingerprint",
    }
    rows_by_kind: dict[str, Mapping[str, Any]] = {}
    expected_files = {"manifest.json"}
    for row in rows:
        if not isinstance(row, Mapping) or set(row) != row_keys:
            raise AffectedBlueprintReadError("projection_schema_invalid: shard manifest row is not exact-current")
        kind = str(row.get("kind", ""))
        if not kind or kind in rows_by_kind:
            raise AffectedBlueprintReadError("projection_identity_mismatch: duplicate projection shard kind")
        relative = _projection_relative_path(row.get("relative_path"), context="projection shard")
        if relative in expected_files:
            raise AffectedBlueprintReadError("projection_identity_mismatch: duplicate projection shard path")
        expected_files.add(relative)
        rows_by_kind[kind] = row

    selected_kinds = {"identity", "affected_index", "behavior_shards", "shared_objects"}
    missing = sorted(selected_kinds - set(rows_by_kind))
    if missing:
        raise AffectedBlueprintReadError(
            "projection_schema_invalid: missing required projection shards: "
            + ", ".join(missing)
        )

    def read_kind(kind: str) -> list[Any]:
        row = rows_by_kind[kind]
        relative = _projection_relative_path(row["relative_path"], context=f"{kind} shard")
        shard = _projection_json_load(
            _projection_file(root, relative, context=f"{kind} shard"),
            context=f"{kind} shard",
        )
        shard_keys = {
            "schema_version",
            "shard_id",
            "kind",
            "relative_path",
            "member_ids",
            "payload",
            "content_fingerprint",
        }
        if set(shard) != shard_keys or shard.get("schema_version") != "1.2":
            raise AffectedBlueprintReadError(f"projection_schema_invalid: {kind} shard is not exact-current")
        for key in row_keys:
            if shard.get(key) != row.get(key):
                raise AffectedBlueprintReadError(
                    f"projection_identity_mismatch: {kind} shard metadata disagrees with manifest"
                )
        payload = shard.get("payload")
        if not isinstance(payload, list):
            raise AffectedBlueprintReadError(f"projection_schema_invalid: {kind} shard payload is not an array")
        if fingerprint_value(payload) != str(row["content_fingerprint"]):
            raise AffectedBlueprintReadError(f"projection_identity_mismatch: {kind} shard content fingerprint mismatch")
        return payload

    identity_rows = read_kind("identity")
    index_rows = read_kind("affected_index")
    if len(identity_rows) != 1 or not isinstance(identity_rows[0], Mapping):
        raise AffectedBlueprintReadError("projection_schema_invalid: identity shard must contain one object")
    identity = dict(identity_rows[0])
    if len(index_rows) != 1 or not isinstance(index_rows[0], Mapping):
        raise AffectedBlueprintReadError("projection_schema_invalid: affected index shard must contain one object")
    index = AffectedBlueprintIndex.from_dict(index_rows[0])
    manifest_blueprint = str(manifest["blueprint_fingerprint"])
    if _projection_identity_value(identity, "blueprint_fingerprint") != manifest_blueprint:
        raise AffectedBlueprintReadError("projection_identity_mismatch: identity blueprint fingerprint disagrees with manifest")
    target_fingerprint = _projection_identity_value(identity, "target_blueprint_fingerprint")
    if target_fingerprint and target_fingerprint != index.blueprint_fingerprint:
        raise AffectedBlueprintReadError("projection_identity_mismatch: target blueprint fingerprint disagrees with affected index")
    child_fingerprints = identity.get("child_fingerprints", {})
    if isinstance(child_fingerprints, Mapping) and child_fingerprints.get("affected_index") not in (None, index.fingerprint):
        raise AffectedBlueprintReadError("projection_identity_mismatch: affected index child fingerprint is stale")

    behavior_locator, shared_locator, _lookup_cache = _load_projection_lookup_cache(
        root,
        authority_root,
        projection_fingerprint=str(manifest["projection_fingerprint"]),
        rows_by_kind=rows_by_kind,
        index=index,
    )
    inventory_rows = read_kind("implementation_inventory") if "implementation_inventory" in rows_by_kind else []

    if set(behavior_locator.row_keys()) != set(dict(index.shard_fingerprints)):
        behavior_locator.close()
        shared_locator.close()
        raise AffectedBlueprintReadError("projection_identity_mismatch: behavior shard set disagrees with affected index")

    expected_objects = dict(index.object_fingerprints)
    observed_object_ids = set(shared_locator.row_keys())
    missing_objects = sorted(set(expected_objects) - observed_object_ids)
    extra_objects = sorted(observed_object_ids - set(expected_objects))
    if missing_objects or extra_objects:
        shared_locator.close()
        behavior_locator.close()
        detail = []
        if missing_objects:
            detail.append("omits: " + ", ".join(missing_objects))
        if extra_objects:
            detail.append("contains unindexed: " + ", ".join(extra_objects))
        raise AffectedBlueprintReadError(
            "projection_identity_mismatch: shared object set " + "; ".join(detail)
        )
    # Do not materialize or hash every shared object/behavior row during
    # ordinary projection admission.  The affected reader asks the bundle for
    # a bounded closure; load_shard/load_object verify the accepted
    # content-addressed fingerprint at that point.  The full canonical
    # projection loader remains the exhaustive integrity gate.

    state, derived_snapshot = _projection_authority_snapshot(Path(authority_root))
    current_snapshot = str(state.snapshot.fingerprint)
    identity_snapshot = _projection_identity_value(identity, "subject_revision")
    software_manifest = identity.get("software_manifest")
    if isinstance(software_manifest, Mapping):
        observed = str(software_manifest.get("observed_snapshot_fingerprint", "") or "")
        if observed and observed != current_snapshot:
            raise AffectedBlueprintReadError("projection_snapshot_identity_mismatch: software manifest snapshot is stale")
    if identity_snapshot and identity_snapshot != current_snapshot:
        raise AffectedBlueprintReadError("projection_snapshot_identity_mismatch: projection subject revision is stale")
    if not identity_snapshot and not isinstance(software_manifest, Mapping):
        raise AffectedBlueprintReadError("projection_snapshot_identity_mismatch: projection has no authority snapshot identity")
    if accepted_snapshot is not None:
        supplied_snapshot = str(accepted_snapshot.get("snapshot_id", accepted_snapshot.get("snapshot_fingerprint", "")) or "")
        supplied_as_of = str(accepted_snapshot.get("as_of", accepted_snapshot.get("subject_revision", "")) or "")
        if supplied_snapshot != current_snapshot or supplied_as_of not in {
            str(state.snapshot.subject_revision),
            str(state.head.subject_revision),
            str(getattr(state.head, "accepted_revision_set_fingerprint", "")),
        }:
            raise AffectedBlueprintReadError("projection_snapshot_identity_mismatch: supplied accepted snapshot is stale")
        supplied_head = str(
            accepted_snapshot.get("authority_head_fingerprint", "") or ""
        )
        if supplied_head and supplied_head != str(state.head.fingerprint):
            raise AffectedBlueprintReadError(
                "projection_snapshot_identity_mismatch: supplied authority head is stale"
            )
        supplied_index = str(
            accepted_snapshot.get(
                "affected_index_fingerprint",
                accepted_snapshot.get(
                    "blueprint_index_fingerprint",
                    accepted_snapshot.get("index_fingerprint", ""),
                ),
            )
            or ""
        )
        if supplied_index and supplied_index != index.fingerprint:
            raise AffectedBlueprintReadError(
                "projection_identity_mismatch: supplied accepted snapshot is bound to another affected index"
            )
        supplied_blueprint = str(
            accepted_snapshot.get(
                "blueprint_fingerprint",
                accepted_snapshot.get("target_blueprint_fingerprint", ""),
            )
            or ""
        )
        if supplied_blueprint and supplied_blueprint != index.blueprint_fingerprint:
            raise AffectedBlueprintReadError(
                "projection_identity_mismatch: supplied accepted snapshot is bound to another blueprint"
            )
    derived_snapshot = {
        **derived_snapshot,
        "affected_index_fingerprint": index.fingerprint,
        "blueprint_fingerprint": index.blueprint_fingerprint,
    }

    surface_catalog: Mapping[str, Any] | None = None
    if inventory_rows:
        if len(inventory_rows) != 1 or not isinstance(inventory_rows[0], Mapping):
            raise AffectedBlueprintReadError("projection_schema_invalid: implementation inventory shard must contain one object")
        inventory = inventory_rows[0]
        surfaces = inventory.get("surfaces", ())
        if surfaces is not None and not isinstance(surfaces, list):
            raise AffectedBlueprintReadError("projection_schema_invalid: implementation inventory surfaces are not an array")
        surface_catalog = dict(inventory)
        surface_catalog["surfaces"] = list(surfaces or ())
        surface_catalog["_flowguard_catalog_identity"] = {
            "affected_index_fingerprint": index.fingerprint,
            "blueprint_fingerprint": index.blueprint_fingerprint,
            "authority_snapshot_fingerprint": current_snapshot,
            "inventory_shard_fingerprint": str(
                rows_by_kind["implementation_inventory"]["content_fingerprint"]
            ),
            "surfaces_fingerprint": fingerprint_value(
                {"surfaces": list(surfaces or ())}
            ),
        }

    unknown_entries: list[str] = []
    pending: list[tuple[Path, str]] = [(root, "")]
    while pending:
        directory, prefix = pending.pop()
        try:
            entries = sorted(os.scandir(directory), key=lambda entry: entry.name)
        except OSError as exc:
            raise AffectedBlueprintReadError(f"projection_read_error: cannot inspect projection entries: {exc}") from exc
        for entry in entries:
            relative = f"{prefix}/{entry.name}" if prefix else entry.name
            relative = PurePosixPath(relative).as_posix()
            try:
                entry_stat = entry.stat(follow_symlinks=False)
            except OSError as exc:
                raise AffectedBlueprintReadError(f"projection_read_error: cannot inspect projection entry {relative}: {exc}") from exc
            if _projection_is_reparse(entry_stat):
                raise AffectedBlueprintReadError(f"projection_path_traversal: projection entry is a reparse point: {relative}")
            if stat.S_ISDIR(entry_stat.st_mode):
                pending.append((Path(entry.path), relative))
            elif stat.S_ISREG(entry_stat.st_mode) and relative not in expected_files:
                unknown_entries.append(relative)
            elif not stat.S_ISREG(entry_stat.st_mode):
                raise AffectedBlueprintReadError(f"projection_schema_invalid: unsupported projection entry: {relative}")

    return AffectedBlueprintProjectionBundle(
        projection_root=root,
        projection_fingerprint=str(manifest["projection_fingerprint"]),
        blueprint_fingerprint=manifest_blueprint,
        index=index,
        shard_payloads=(),
        object_payloads=(),
        identity=identity,
        surface_catalog=surface_catalog,
        accepted_snapshot=derived_snapshot,
        authority_snapshot_fingerprint=current_snapshot,
        authority_head_fingerprint=str(state.head.fingerprint),
        unknown_entries=tuple(sorted(unknown_entries)),
        object_ids=tuple(sorted(observed_object_ids)),
        object_locator=shared_locator,
        shard_locator=behavior_locator,
        authority_state=state,
    )


def _put_content_addressed_object(
    objects: dict[str, Any], object_id: str, payload: Any
) -> None:
    existing = objects.get(object_id, _MISSING)
    if existing is not _MISSING and existing != payload:
        raise AffectedBlueprintReadError(
            f"normalized object identity collision: {object_id}"
        )
    objects[object_id] = payload


def _materialize_topology_invalidation_edges(
    objects: Mapping[str, Any],
    *,
    include_sibling_invalidation: bool = False,
) -> tuple[
    tuple[AffectedTopologyInvalidationEdge, ...],
    dict[str, set[str]],
]:
    """Project exact typed topology dependencies without scanning target source."""

    nodes: dict[str, tuple[str, tuple[str, ...]]] = {}
    topology_relations: list[tuple[str, str, str, str, str]] = []
    for object_id, value in sorted(objects.items()):
        if not isinstance(value, Mapping):
            continue
        kind = str(value.get("kind", ""))
        if kind == "blueprint_topology_node":
            node_id = _string(
                value.get("node_id"),
                context=f"topology node identity {object_id}",
            )
            if node_id in nodes:
                raise AffectedBlueprintReadError(
                    f"duplicate topology node identity: {node_id}"
                )
            surfaces = tuple(
                sorted(
                    _string_array(
                        value.get("implementation_surface_ids", ()),
                        context=f"topology node surfaces {node_id}",
                    )
                )
            )
            nodes[node_id] = (object_id, surfaces)
        elif kind == "blueprint_topology_relation":
            relation_kind = str(value.get("relation_kind", ""))
            if relation_kind not in TOPOLOGY_RELATION_KINDS:
                # The topology owner retains the unknown-kind finding.  An
                # invalid relation cannot become an invalidation authority.
                continue
            topology_relations.append(
                (
                    _string(
                        value.get("relation_id"),
                        context=f"topology relation identity {object_id}",
                    ),
                    relation_kind,
                    _string(
                        value.get("producer_id"),
                        context=f"topology relation producer {object_id}",
                    ),
                    _string(
                        value.get("consumer_id"),
                        context=f"topology relation consumer {object_id}",
                    ),
                    object_id,
                )
            )

    edge_evidence: dict[tuple[str, str, str, str], set[str]] = {}
    object_edges: dict[str, set[str]] = {}

    def add_edge(
        source_id: str,
        target_id: str,
        edge_kind: str,
        evidence_object_ids: tuple[str, ...],
        *,
        via_node_id: str = "",
    ) -> None:
        object_edges.setdefault(source_id, set()).update(
            evidence_object_ids
        )
        object_edges.setdefault(target_id, set()).update(
            evidence_object_ids
        )
        if source_id == target_id:
            # A feedback self-loop carries evidence but expands no new seed.
            return
        identity = (source_id, target_id, edge_kind, via_node_id)
        edge_evidence.setdefault(identity, set()).update(evidence_object_ids)

    for node_id, (node_object_id, surface_ids) in sorted(nodes.items()):
        object_edges.setdefault(node_id, set()).add(node_object_id)
        for surface_id in surface_ids:
            object_edges.setdefault(surface_id, set()).add(node_object_id)
            add_edge(
                surface_id,
                node_id,
                "realization_owner",
                (node_object_id,),
                via_node_id=node_id,
            )
            add_edge(
                node_id,
                surface_id,
                "realization_member",
                (node_object_id,),
                via_node_id=node_id,
            )

    children_by_parent: dict[str, dict[str, set[str]]] = {}
    for (
        relation_id,
        relation_kind,
        producer_id,
        consumer_id,
        relation_object_id,
    ) in topology_relations:
        if producer_id not in nodes or consumer_id not in nodes:
            # The topology owner retains the exact endpoint gap. An invalid
            # relation cannot become an invalidation authority here.
            continue
        object_edges.setdefault(relation_id, set()).add(relation_object_id)
        add_edge(
            relation_id,
            producer_id,
            "relation_producer",
            (relation_object_id,),
        )
        add_edge(
            relation_id,
            consumer_id,
            "relation_consumer",
            (relation_object_id,),
        )
        if relation_kind == "child_to_parent":
            children_by_parent.setdefault(consumer_id, {}).setdefault(
                producer_id, set()
            ).add(relation_object_id)
            add_edge(
                producer_id,
                consumer_id,
                "ancestor",
                (relation_object_id,),
                via_node_id=consumer_id,
            )
            add_edge(
                consumer_id,
                producer_id,
                "child",
                (relation_object_id,),
                via_node_id=consumer_id,
            )
        else:
            # Producer output and support flow downstream.  Delegation is a
            # dependency in the other direction: a changed delegate invalidates
            # its delegator.  The relation seed above always reviews both ends.
            direction = _TOPOLOGY_RELATION_INVALIDATION_DIRECTIONS.get(relation_kind)
            if direction is None:
                raise AffectedBlueprintReadError(
                    "topology relation has no explicit invalidation direction: "
                    + relation_kind
                )
            invalidation_source_id, invalidation_target_id = (
                (consumer_id, producer_id)
                if direction == "consumer_to_producer"
                else (producer_id, consumer_id)
            )
            add_edge(
                invalidation_source_id,
                invalidation_target_id,
                relation_kind,
                (relation_object_id,),
            )

    # A child-to-parent edge is enough to close the changed child over its
    # ancestors.  Reopening every sibling is a broader *family* review and is
    # therefore opt-in; the affected-only reader must not silently turn one
    # changed model into an unrelated sibling fanout.
    if not include_sibling_invalidation:
        children_by_parent.clear()

    for parent_id, child_rows in sorted(children_by_parent.items()):
        ordered_children = sorted(
            (child_id, tuple(sorted(relation_ids)))
            for child_id, relation_ids in child_rows.items()
        )
        if len(ordered_children) < 2:
            continue
        # A canonical star preserves exact sibling reachability from every
        # child while keeping the frozen index linear in sibling count.  The
        # former all-pairs expansion added k*(k-1) rows and duplicated the
        # same parent evidence throughout large, flat model families.
        anchor_id, anchor_relation_ids = ordered_children[0]
        for sibling_id, sibling_relation_ids in ordered_children[1:]:
            evidence_ids = tuple(
                sorted((*anchor_relation_ids, *sibling_relation_ids))
            )
            add_edge(
                anchor_id,
                sibling_id,
                "sibling",
                evidence_ids,
                via_node_id=parent_id,
            )
            add_edge(
                sibling_id,
                anchor_id,
                "sibling",
                evidence_ids,
                via_node_id=parent_id,
            )

    edges = tuple(
        AffectedTopologyInvalidationEdge(
            source_id=source_id,
            target_id=target_id,
            edge_kind=edge_kind,
            evidence_object_ids=tuple(sorted(evidence_ids)),
            via_node_id=via_node_id,
        )
        for (
            source_id,
            target_id,
            edge_kind,
            via_node_id,
        ), evidence_ids in sorted(edge_evidence.items())
    )
    return edges, object_edges


def materialize_affected_blueprint_index(
    projection: Any,
    *,
    target_system_id: str,
    target_profile: str,
    subject_revision: str,
    descriptor_fingerprint: str,
    target_blueprint_fingerprint: str,
    layer_plan_id: str,
    layer_plan_fingerprint: str,
    readiness_ledger: BlueprintReadinessLedger,
    shared_objects: Mapping[str, Any],
    required_path_quality_model_ids: Iterable[str] = (),
    include_sibling_invalidation: bool = False,
) -> tuple[AffectedBlueprintIndex, tuple[tuple[str, Any], ...]]:
    """Add a separately addressed ledger index without mutating base authority."""

    for name, value in (
        ("target system id", target_system_id),
        ("target profile", target_profile),
        ("subject revision", subject_revision),
        ("descriptor fingerprint", descriptor_fingerprint),
        ("target blueprint fingerprint", target_blueprint_fingerprint),
        ("layer plan id", layer_plan_id),
        ("layer plan fingerprint", layer_plan_fingerprint),
    ):
        _string(value, context=f"affected blueprint {name}")
    objects = {str(key): item for key, item in shared_objects.items()}
    base_object_fingerprints = {
        key: str(value)
        for key, value in _index_pairs(
            _field(projection, "object_fingerprints", ()),
            context="object fingerprint index",
        ).items()
    }
    object_fingerprint_by_id: dict[str, str] = {}
    for object_id, expected in base_object_fingerprints.items():
        if object_id not in objects:
            raise AffectedBlueprintReadError(
                f"normalized shared object is missing: {object_id}"
            )
        actual = fingerprint_value(objects[object_id])
        if actual != expected:
            raise AffectedBlueprintReadError(
                f"normalized shared object fingerprint mismatch: {object_id}"
            )
        object_fingerprint_by_id[object_id] = actual

    # A supplied shared-object mapping may contain extra current objects that
    # are not named by the normalized projection. Preserve the existing
    # behavior, but fingerprint each exact payload only once in this invocation.
    for object_id, payload in objects.items():
        if object_id not in object_fingerprint_by_id:
            object_fingerprint_by_id[object_id] = fingerprint_value(payload)

    def put_indexed_object(
        object_id: str,
        payload: Any,
        *,
        precomputed_fingerprint: str | None = None,
    ) -> str:
        _put_content_addressed_object(objects, object_id, payload)
        existing = object_fingerprint_by_id.get(object_id)
        if existing is not None:
            if (
                precomputed_fingerprint is not None
                and precomputed_fingerprint != existing
            ):
                raise AffectedBlueprintReadError(
                    f"normalized object fingerprint collision: {object_id}"
                )
            return existing
        actual = (
            precomputed_fingerprint
            if precomputed_fingerprint is not None
            else fingerprint_value(payload)
        )
        object_fingerprint_by_id[object_id] = actual
        return actual

    native_object_ids: dict[tuple[str, str, str], str] = {}
    for row in readiness_ledger.rows:
        for native in row.native_reports:
            identity = (
                native.owner_id,
                native.report_id,
                native.report_fingerprint,
            )
            if identity in native_object_ids:
                continue
            payload = {
                "kind": "blueprint_native_report",
                "owner_id": native.owner_id,
                "report_id": native.report_id,
                "report_fingerprint": native.report_fingerprint,
            }
            payload_fingerprint = fingerprint_value(payload)
            object_id = (
                "blueprint-native-report:"
                + payload_fingerprint.split(":", 1)[-1]
            )
            put_indexed_object(
                object_id,
                payload,
                precomputed_fingerprint=payload_fingerprint,
            )
            native_object_ids[identity] = object_id

    for gap in readiness_ledger.gaps:
        gap_payload = {
            "kind": "blueprint_gap",
            "gap_id": gap.gap_id,
            **gap.to_dict(),
        }
        put_indexed_object(
            gap.gap_id,
            gap_payload,
        )

    ledger_row_ids: list[str] = []
    for row in readiness_ledger.rows:
        native_ids = tuple(
            native_object_ids[
                (native.owner_id, native.report_id, native.report_fingerprint)
            ]
            for native in row.native_reports
        )
        payload = {
            "kind": "blueprint_readiness_row",
            "layer": row.layer,
            "status": row.status,
            "evidence_ids": list(row.evidence_ids),
            "gap_ids": list(row.gap_ids),
            "native_report_object_ids": list(native_ids),
            "pre_code_status": row.pre_code_status,
            "executed_evidence_status": row.executed_evidence_status,
            "implementation_admitted": row.implementation_admitted,
            "referenced_object_ids": [*row.gap_ids, *native_ids],
        }
        payload_fingerprint = fingerprint_value(payload)
        row_id = (
            "blueprint-readiness-row:"
            + payload_fingerprint.split(":", 1)[-1]
        )
        put_indexed_object(
            row_id,
            payload,
            precomputed_fingerprint=payload_fingerprint,
        )
        ledger_row_ids.append(row_id)

    target_payload = {
        "kind": "affected_blueprint_target",
        "target_system_id": str(target_system_id),
        "target_profile": str(target_profile),
        "subject_revision": str(subject_revision),
        "descriptor_fingerprint": str(descriptor_fingerprint),
        "blueprint_fingerprint": str(target_blueprint_fingerprint),
        "logical_fingerprint": str(_field(projection, "logical_fingerprint")),
        "layer_plan_id": str(layer_plan_id),
        "layer_plan_fingerprint": str(layer_plan_fingerprint),
        "required_path_quality_model_ids": list(
            sorted(
                _string_array(
                    tuple(required_path_quality_model_ids),
                    context="required path-quality model ids",
                )
            )
        ),
        "ledger_row_ids": list(ledger_row_ids),
        "referenced_object_ids": list(ledger_row_ids),
    }
    target_payload_fingerprint = fingerprint_value(target_payload)
    target_object_id = (
        "affected-blueprint-target:"
        + target_payload_fingerprint.split(":", 1)[-1]
    )
    put_indexed_object(
        target_object_id,
        target_payload,
        precomputed_fingerprint=target_payload_fingerprint,
    )

    topology_invalidation_edges, topology_object_edges = (
        _materialize_topology_invalidation_edges(
            objects,
            include_sibling_invalidation=include_sibling_invalidation,
        )
    )

    shard_members = tuple(
        sorted(
            (str(shard_id), tuple(sorted(set(_ids(member_ids)))))
            for shard_id, member_ids in _index_pairs(
                _field(projection, "shard_member_ids", ()),
                context="shard member index",
            ).items()
        )
    )
    affected_member_ids = {
        member_id for _shard_id, member_ids in shard_members for member_id in member_ids
    } | set(base_object_fingerprints) | set(topology_object_edges)
    # Each affected edge points once to the target object; that object owns the
    # ordered ledger references.  Repeating every row on every edge would make
    # the index grow as affected-members x layers without adding authority.
    affected_object_edges = {
        affected_id: {target_object_id}
        for affected_id in affected_member_ids
    }
    for affected_id, object_ids in topology_object_edges.items():
        affected_object_edges.setdefault(affected_id, {target_object_id}).update(
            object_ids
        )
    index = AffectedBlueprintIndex(
        blueprint_fingerprint=str(target_blueprint_fingerprint),
        logical_fingerprint=str(_field(projection, "logical_fingerprint")),
        target_object_id=target_object_id,
        ledger_row_ids=tuple(ledger_row_ids),
        object_fingerprints=tuple(sorted(object_fingerprint_by_id.items())),
        shard_fingerprints=tuple(
            sorted(
                (str(key), str(value))
                for key, value in _index_pairs(
                    _field(projection, "shard_fingerprints", ()),
                    context="shard fingerprint index",
                ).items()
            )
        ),
        shard_member_ids=shard_members,
        affected_edges=tuple(
            (affected_id, tuple(sorted(object_ids)))
            for affected_id, object_ids in sorted(affected_object_edges.items())
        ),
        topology_invalidation_edges=topology_invalidation_edges,
    )
    return index, tuple(sorted(objects.items()))


@dataclass(frozen=True)
class AffectedBlueprintReadResult:
    blueprint_fingerprint: str
    logical_fingerprint: str
    requested_seed_ids: tuple[str, ...]
    affected_ids: tuple[str, ...]
    propagated_affected_ids: tuple[str, ...]
    shard_ids: tuple[str, ...]
    object_ids: tuple[str, ...]
    ancestor_object_ids: tuple[str, ...]
    shards: tuple[tuple[str, Any], ...]
    objects: tuple[tuple[str, Any], ...]
    # Exact topology edges actually traversed from the requested seeds.  This
    # is intentionally retained with the read result so later projections do
    # not rebuild a broader graph walk and accidentally reopen unrelated
    # siblings.
    traversed_topology_edge_identities: tuple[tuple[str, str, str, str], ...] = ()
    # Deterministic reason paths selected during that same traversal. Each
    # row is ``(seed_id, node_ids, edge_identities)``. A later task-context
    # projection consumes these rows directly instead of running a second BFS
    # that could lose the child-descent state of the bounded closure.
    traversed_topology_paths: tuple[
        tuple[
            str,
            tuple[str, ...],
            tuple[tuple[str, str, str, str], ...],
        ],
        ...,
    ] = ()

    @property
    def schema_version(self) -> str:
        return AFFECTED_BLUEPRINT_READER_SCHEMA

    @cached_property
    def fingerprint(self) -> str:
        return fingerprint_value(self.identity_payload())

    @property
    def claim_boundary(self) -> str:
        return (
            "This result proves only the fingerprint-checked affected shards, "
            "their referenced objects, and required ancestors. It neither "
            "constructs nor qualifies the whole blueprint."
        )

    def identity_payload(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "blueprint_fingerprint": self.blueprint_fingerprint,
            "logical_fingerprint": self.logical_fingerprint,
            "requested_seed_ids": list(self.requested_seed_ids),
            "affected_ids": list(self.affected_ids),
            "propagated_affected_ids": list(self.propagated_affected_ids),
            "shard_ids": list(self.shard_ids),
            "object_ids": list(self.object_ids),
            "ancestor_object_ids": list(self.ancestor_object_ids),
            "traversed_topology_edge_identities": [
                list(identity) for identity in self.traversed_topology_edge_identities
            ],
            "traversed_topology_paths": [
                {
                    "seed_id": seed_id,
                    "node_ids": list(node_ids),
                    "edge_identities": [
                        list(identity) for identity in edge_identities
                    ],
                }
                for seed_id, node_ids, edge_identities
                in self.traversed_topology_paths
            ],
            "shards": dict(self.shards),
            "objects": dict(self.objects),
            "claim_boundary": self.claim_boundary,
        }

    def to_dict(self) -> dict[str, Any]:
        return {**self.identity_payload(), "fingerprint": self.fingerprint}


class AffectedBlueprintReader:
    """Read one exact affected closure without a whole-blueprint fallback."""

    def __init__(
        self,
        projection: Any,
        *,
        load_shard: ShardLoader,
        load_object: ObjectLoader,
    ) -> None:
        if not callable(load_shard) or not callable(load_object):
            raise AffectedBlueprintReadError("shard and object loaders must be callable")
        self._projection = projection
        self._load_shard = load_shard
        self._load_object = load_object
        self._shard_fingerprints = {
            key: str(value)
            for key, value in _index_pairs(
                getattr(projection, "shard_fingerprints", ()),
                context="shard fingerprint index",
            ).items()
        }
        self._object_fingerprints = {
            key: str(value)
            for key, value in _index_pairs(
                getattr(projection, "object_fingerprints", ()),
                context="object fingerprint index",
            ).items()
        }
        raw_members = _index_pairs(
            getattr(projection, "shard_member_ids", ()),
            context="shard member index",
        )
        self._shard_members = {
            shard_id: tuple(sorted(set(_ids(member_ids))))
            for shard_id, member_ids in raw_members.items()
        }
        raw_edges = _index_pairs(
            _field(projection, "affected_edges", ()),
            context="affected edge index",
        )
        self._affected_edges = {
            affected_id: tuple(sorted(set(_ids(object_ids))))
            for affected_id, object_ids in raw_edges.items()
        }
        raw_topology_edges = tuple(
            _field(projection, "topology_invalidation_edges", ())
        )
        if any(
            not isinstance(row, AffectedTopologyInvalidationEdge)
            for row in raw_topology_edges
        ):
            raise AffectedBlueprintReadError(
                "topology invalidation edges require current typed records"
            )
        self._topology_invalidation_edges = tuple(
            sorted(
                raw_topology_edges,
                key=lambda row: (*row.identity, row.evidence_object_ids),
            )
        )
        self._topology_edges_by_source: dict[
            str, tuple[AffectedTopologyInvalidationEdge, ...]
        ] = {}
        grouped_topology_edges: dict[
            str, list[AffectedTopologyInvalidationEdge]
        ] = {}
        for edge in self._topology_invalidation_edges:
            grouped_topology_edges.setdefault(edge.source_id, []).append(edge)
        self._topology_edges_by_source = {
            source_id: tuple(rows)
            for source_id, rows in grouped_topology_edges.items()
        }
        missing_shards = sorted(
            set(self._shard_members) - set(self._shard_fingerprints)
        )
        if missing_shards:
            raise AffectedBlueprintReadError(
                "shard member index has no fingerprint for: "
                + ", ".join(missing_shards)
            )
        missing_edge_objects = sorted(
            {
                object_id
                for object_ids in self._affected_edges.values()
                for object_id in object_ids
                if object_id not in self._object_fingerprints
            }
        )
        if missing_edge_objects:
            raise AffectedBlueprintReadError(
                "affected edge index references unaddressed objects: "
                + ", ".join(missing_edge_objects)
            )
        missing_topology_evidence = sorted(
            {
                object_id
                for edge in self._topology_invalidation_edges
                for object_id in edge.evidence_object_ids
                if object_id not in self._object_fingerprints
            }
        )
        if missing_topology_evidence:
            raise AffectedBlueprintReadError(
                "topology invalidation edges reference unaddressed evidence: "
                + ", ".join(missing_topology_evidence)
            )

    def read(self, affected_ids: Iterable[str]) -> AffectedBlueprintReadResult:
        requested = tuple(sorted({str(value) for value in affected_ids if str(value)}))
        if not requested:
            raise AffectedBlueprintReadError("affected ids must not be empty")

        requested_set = set(requested)
        indexed_members = {
            member_id
            for member_ids in self._shard_members.values()
            for member_id in member_ids
        }
        known_affected_ids = {
            *indexed_members,
            *self._object_fingerprints,
            *self._affected_edges,
            *(edge.source_id for edge in self._topology_invalidation_edges),
            *(edge.target_id for edge in self._topology_invalidation_edges),
        }
        unknown = sorted(requested_set - known_affected_ids)
        if unknown:
            raise AffectedBlueprintReadError(
                "unknown affected ids: " + ", ".join(unknown)
            )

        propagated_set = set(requested_set)
        # ``child`` edges are intentionally context-sensitive.  A caller that
        # explicitly asks for a parent gets its required descendants, but a
        # child that propagates upward to that parent must not immediately
        # fan back down into unrelated siblings.  Keep a small traversal mode
        # alongside each id so the static edge index can express both cases
        # without reopening a whole model family.
        pending_affected = deque(
            (item, True, (item,), ()) for item in requested
        )
        processed_child_descent: dict[str, bool] = {}
        traversed_topology_edges: set[tuple[str, str, str, str]] = set()
        traversed_topology_paths: dict[
            tuple[str, str, str, str],
            tuple[str, tuple[str, ...], tuple[tuple[str, str, str, str], ...]],
        ] = {}
        while pending_affected:
            (
                source_id,
                allow_child_descent,
                node_path,
                edge_path,
            ) = pending_affected.popleft()
            previous_descent = processed_child_descent.get(source_id)
            if previous_descent is True or (
                previous_descent is False and not allow_child_descent
            ):
                continue
            processed_child_descent[source_id] = bool(
                allow_child_descent or previous_descent is True
            )
            for edge in self._topology_edges_by_source.get(source_id, ()):
                if edge.edge_kind == "child" and not allow_child_descent:
                    continue
                traversed_topology_edges.add(edge.identity)
                candidate_node_path = (*node_path, edge.target_id)
                candidate_edge_path = (*edge_path, edge.identity)
                candidate_path = (
                    node_path[0],
                    candidate_node_path,
                    candidate_edge_path,
                )
                existing_path = traversed_topology_paths.get(edge.identity)
                if existing_path is None or (
                    len(candidate_edge_path),
                    candidate_edge_path,
                    candidate_path[0],
                    candidate_node_path,
                ) < (
                    len(existing_path[2]),
                    existing_path[2],
                    existing_path[0],
                    existing_path[1],
                ):
                    traversed_topology_paths[edge.identity] = candidate_path
                # A cycle edge remains part of the actual selected boundary,
                # but it must not enqueue a node already on this path and
                # reopen the same cycle indefinitely.
                if edge.target_id in node_path:
                    continue
                if edge.target_id in propagated_set:
                    # An already reached id may still need one pass with the
                    # broader explicit-parent descent mode.
                    target_allow_child_descent = bool(
                        allow_child_descent
                        and edge.edge_kind
                        in {"child", "realization_owner", "realization_member"}
                    )
                    pending_affected.append(
                        (
                            edge.target_id,
                            target_allow_child_descent,
                            candidate_node_path,
                            candidate_edge_path,
                        )
                    )
                    continue
                propagated_set.add(edge.target_id)
                pending_affected.append(
                    (
                        edge.target_id,
                        bool(
                            allow_child_descent
                            and edge.edge_kind
                            in {"child", "realization_owner", "realization_member"}
                        ),
                        candidate_node_path,
                        candidate_edge_path,
                    )
                )
        affected = tuple(sorted(propagated_set))
        affected_set = set(affected)
        selected_shards = tuple(
            sorted(
                shard_id
                for shard_id, member_ids in self._shard_members.items()
                if affected_set.intersection(member_ids)
            )
        )
        directly_indexed_objects = affected_set.intersection(
            self._object_fingerprints
        )
        edge_indexed_ids = affected_set.intersection(self._affected_edges)

        loaded_shards: list[tuple[str, Any]] = []
        pending_objects: set[str] = set(directly_indexed_objects)
        for affected_id in edge_indexed_ids:
            pending_objects.update(self._affected_edges[affected_id])
        allowed_topology_object_ids = {
            object_id
            for affected_id in edge_indexed_ids
            for object_id in self._affected_edges[affected_id]
            if object_id.startswith("topology-")
        }
        ancestor_ids: set[str] = set()
        for shard_id in selected_shards:
            try:
                payload = self._load_shard(shard_id)
            except Exception as exc:
                raise AffectedBlueprintReadError(
                    f"failed to load affected shard {shard_id}: {exc}"
                ) from exc
            if fingerprint_value(payload) != self._shard_fingerprints[shard_id]:
                raise AffectedBlueprintReadError(
                    f"shard fingerprint mismatch: {shard_id}"
                )
            payload = _reference_shard(payload, shard_id=shard_id)
            loaded_shards.append((shard_id, payload))
            explicit, inferred, ancestors = _discover_links(payload)
            if (
                isinstance(payload, Mapping)
                and payload.get("kind") == "blueprint_topology_index"
            ):
                inferred = {
                    object_id
                    for object_id in inferred
                    if not object_id.startswith("topology-relation:")
                    or object_id in allowed_topology_object_ids
                }
            missing_explicit = sorted(explicit - set(self._object_fingerprints))
            if missing_explicit:
                raise AffectedBlueprintReadError(
                    f"shard {shard_id} references unindexed objects: "
                    + ", ".join(missing_explicit)
                )
            pending_objects.update(explicit)
            pending_objects.update(inferred.intersection(self._object_fingerprints))
            ancestor_ids.update(ancestors.intersection(self._object_fingerprints))

        queue = deque(sorted(pending_objects))
        queued = set(queue)
        loaded_objects: list[tuple[str, Any]] = []
        loaded_object_ids: set[str] = set()
        while queue:
            object_id = queue.popleft()
            if object_id in loaded_object_ids:
                continue
            try:
                payload = self._load_object(object_id)
            except Exception as exc:
                raise AffectedBlueprintReadError(
                    f"failed to load referenced object {object_id}: {exc}"
                ) from exc
            if fingerprint_value(payload) != self._object_fingerprints[object_id]:
                raise AffectedBlueprintReadError(
                    f"object fingerprint mismatch: {object_id}"
                )
            loaded_objects.append((object_id, payload))
            loaded_object_ids.add(object_id)
            explicit, inferred, ancestors = _discover_links(payload)
            if (
                isinstance(payload, Mapping)
                and payload.get("kind") == "blueprint_topology_index"
            ):
                inferred = {
                    discovered_id
                    for discovered_id in inferred
                    if not discovered_id.startswith("topology-relation:")
                    or discovered_id in allowed_topology_object_ids
                }
            missing_explicit = sorted(explicit - set(self._object_fingerprints))
            if missing_explicit:
                raise AffectedBlueprintReadError(
                    f"object {object_id} references unindexed objects: "
                    + ", ".join(missing_explicit)
                )
            discovered = explicit | inferred.intersection(self._object_fingerprints)
            ancestor_ids.update(
                (ancestors - {object_id}).intersection(
                    self._object_fingerprints
                )
            )
            for discovered_id in sorted(discovered):
                if discovered_id not in loaded_object_ids and discovered_id not in queued:
                    queue.append(discovered_id)
                    queued.add(discovered_id)

        return AffectedBlueprintReadResult(
            blueprint_fingerprint=str(
                _field(self._projection, "blueprint_fingerprint", "")
            ),
            logical_fingerprint=str(
                _field(self._projection, "logical_fingerprint", "")
            ),
            requested_seed_ids=requested,
            affected_ids=affected,
            propagated_affected_ids=tuple(
                sorted(affected_set - requested_set)
            ),
            shard_ids=tuple(row[0] for row in loaded_shards),
            object_ids=tuple(row[0] for row in loaded_objects),
            ancestor_object_ids=tuple(
                sorted(ancestor_ids.intersection(loaded_object_ids))
            ),
            shards=tuple(loaded_shards),
            objects=tuple(loaded_objects),
            traversed_topology_edge_identities=tuple(
                sorted(traversed_topology_edges)
            ),
            traversed_topology_paths=tuple(
                sorted(
                    traversed_topology_paths.values(),
                    key=lambda row: (
                        row[0],
                        len(row[2]),
                        row[2],
                        row[1],
                    ),
                )
            ),
        )


def read_affected_blueprint(
    projection: Any,
    *,
    affected_ids: Iterable[str],
    load_shard: ShardLoader,
    load_object: ObjectLoader,
) -> AffectedBlueprintReadResult:
    """Convenience function for one bounded affected read."""

    return AffectedBlueprintReader(
        projection,
        load_shard=load_shard,
        load_object=load_object,
    ).read(affected_ids)


_TARGET_FIELDS = frozenset(
    {
        "kind",
        "target_system_id",
        "target_profile",
        "subject_revision",
        "descriptor_fingerprint",
        "blueprint_fingerprint",
        "logical_fingerprint",
        "layer_plan_id",
        "layer_plan_fingerprint",
        "required_path_quality_model_ids",
        "ledger_row_ids",
        "referenced_object_ids",
    }
)
_ROW_FIELDS = frozenset(
    {
        "kind",
        "layer",
        "status",
        "evidence_ids",
        "gap_ids",
        "native_report_object_ids",
        "pre_code_status",
        "executed_evidence_status",
        "implementation_admitted",
        "referenced_object_ids",
    }
)
_GAP_FIELDS = frozenset(
    {
        "kind",
        "gap_id",
        "layer",
        "object_kind",
        "object_id",
        "status",
        "owner_id",
        "evidence_ref",
        "expected_fingerprint",
        "observed_fingerprint",
        "message",
    }
)
_NATIVE_REPORT_FIELDS = frozenset(
    {"kind", "owner_id", "report_id", "report_fingerprint"}
)


def _context_stored(value: Any, name: str, default: Any = None) -> Any:
    """Read task-map data without invoking arbitrary object properties."""

    if isinstance(value, Mapping):
        return value.get(name, default)
    namespace = getattr(value, "__dict__", None)
    if isinstance(namespace, dict):
        return namespace.get(name, default)
    return default


def _context_rows(value: Any, *names: str) -> tuple[Any, ...]:
    """Extract an already-materialized record collection from a catalog."""

    candidate = value
    if value is not None and not isinstance(value, (Mapping, Sequence)):
        for name in names:
            candidate = _context_stored(value, name, _MISSING)
            if candidate is not _MISSING:
                break
        else:
            return ()
    elif isinstance(value, Mapping):
        for name in names:
            if name in value:
                candidate = value[name]
                break
        else:
            # A mapping keyed by record identity is itself a catalog.
            candidate = value
    if candidate is None or candidate is _MISSING:
        return ()
    if isinstance(candidate, Mapping):
        # A single record is distinguishable from an id -> record catalog by
        # its identity fields.  Preserve the key so callers can recover the
        # surface id when the payload omits it.
        if any(key in candidate for key in ("surface_id", "implementation_surface_id")):
            return (candidate,)
        rows: list[Any] = []
        for key, row in candidate.items():
            if isinstance(row, Mapping):
                payload = dict(row)
                payload.setdefault("surface_id", str(key))
                rows.append(payload)
            else:
                rows.append(row)
        return tuple(rows)
    if isinstance(candidate, Sequence) and not isinstance(
        candidate, (str, bytes, bytearray)
    ):
        return tuple(candidate)
    return ()


def _context_scalar(value: Any, *names: str, default: Any = "") -> Any:
    for name in names:
        supplied = _context_stored(value, name, _MISSING)
        if supplied is not _MISSING and supplied not in (None, ""):
            return supplied
    return default


def _context_strings(value: Any, *names: str) -> list[str]:
    for name in names:
        supplied = _context_stored(value, name, _MISSING)
        if supplied is _MISSING or supplied is None:
            continue
        if isinstance(supplied, str):
            return [supplied] if supplied else []
        if isinstance(supplied, Sequence) and not isinstance(
            supplied, (bytes, bytearray)
        ):
            return sorted({str(item) for item in supplied if str(item)})
    return []


def _context_bool(value: Any, *names: str, default: bool = False) -> bool:
    for name in names:
        supplied = _context_stored(value, name, _MISSING)
        if supplied is _MISSING:
            continue
        return supplied if isinstance(supplied, bool) else default
    return default


def _context_safe(value: Any, *, depth: int = 0) -> Any:
    """Make a bounded, JSON-shaped copy of a canonical object payload."""

    if depth > 8:
        return "<depth-limit>"
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Mapping):
        return {
            str(key): _context_safe(item, depth=depth + 1)
            for key, item in sorted(value.items(), key=lambda row: str(row[0]))
        }
    if isinstance(value, Sequence) and not isinstance(
        value, (str, bytes, bytearray)
    ):
        return [_context_safe(item, depth=depth + 1) for item in value]
    namespace = getattr(value, "__dict__", None)
    if isinstance(namespace, dict):
        return _context_safe(namespace, depth=depth + 1)
    return str(value)


def _context_id(value: Any, *names: str) -> str:
    supplied = _context_scalar(value, *names, default="")
    return str(supplied) if supplied not in (None, "") else ""


def _context_ref(value: Any, *names: str) -> dict[str, Any]:
    return {
        name: str(supplied)
        for name in names
        if (supplied := _context_scalar(value, name, default="")) not in (None, "")
    }


def _context_path(value: Any) -> tuple[str, str]:
    raw = str(_context_scalar(value, "path", default="") or "")
    normalized = raw.replace("\\", "/")
    if not normalized:
        return "", ""
    candidate = PurePosixPath(normalized)
    if candidate.is_absolute() or ".." in candidate.parts:
        return normalized, "invalid_surface_path"
    return candidate.as_posix(), ""


def _context_source_fingerprint(value: Any) -> str:
    supplied = _context_scalar(
        value,
        "source_fingerprint",
        "content_fingerprint",
        "structure_fingerprint",
        "implementation_fingerprint",
        "fingerprint",
        default="",
    )
    return str(supplied) if supplied not in (None, "") else ""


def _context_int(value: Any, *names: str, default: int = 0) -> int:
    supplied = _context_scalar(value, *names, default=default)
    try:
        return int(supplied or 0)
    except (TypeError, ValueError):
        return default


def _context_surface_payload(
    surface_id: str,
    value: Any,
    *,
    owner_id: str = "",
    source_ref: str = "",
) -> dict[str, Any]:
    path, path_gap = _context_path(value)
    payload: dict[str, Any] = {
        "surface_id": surface_id,
        "path": path,
        "symbol": str(_context_scalar(value, "symbol", default="") or ""),
        "surface_kind": str(
            _context_scalar(value, "surface_kind", "kind", default="") or ""
        ),
        "parent_surface_id": str(
            _context_scalar(value, "parent_surface_id", default="") or ""
        ),
        "line_start": _context_int(value, "line_start", default=0),
        "line_end": _context_int(value, "line_end", default=0),
        "owner_id": owner_id
        or str(_context_scalar(value, "owner_id", "behavior_owner_id", default="") or ""),
        "source_fingerprint": _context_source_fingerprint(value),
        "roles": _context_strings(value, "roles"),
        "parameters": _context_strings(value, "parameters"),
        "calls": _context_strings(value, "calls"),
        "state_reads": _context_strings(value, "state_reads"),
        "state_writes": _context_strings(value, "state_writes"),
        "side_effect_candidates": _context_strings(
            value, "side_effect_candidates", "effects", "side_effects"
        ),
        "raised_errors": _context_strings(value, "raised_errors", "errors"),
        "source_ref": source_ref or surface_id,
        "evidence_class": "observed_structure",
    }
    if path_gap:
        payload["path_gap"] = path_gap
    return payload


def _context_objects(read_result: AffectedBlueprintReadResult) -> dict[str, Any]:
    return {str(object_id): value for object_id, value in read_result.objects}


def _context_behavior_blocks(objects: Mapping[str, Any]) -> tuple[tuple[str, Any], ...]:
    return tuple(
        sorted(
            (
                object_id,
                value,
            )
            for object_id, value in objects.items()
            if isinstance(value, Mapping) and value.get("kind") == "behavior_block"
        )
    )


def _context_related_ids(block: Any, *names: str) -> tuple[str, ...]:
    result: set[str] = set()
    for name in names:
        result.update(_context_strings(block, name))
    return tuple(sorted(result))


def _context_placeholder(value: Any) -> bool:
    text = str(value).strip().lower()
    return bool(
        text
        and (
            "owner-defined" in text
            or "preserve state and effect boundaries licensed" in text
            or "template" in text
            or text in {"todo", "tbd", "placeholder"}
            or text.startswith(("todo:", "tbd:", "placeholder:"))
        )
    )


def _context_has_structured_contract(value: Any) -> bool:
    if not isinstance(value, Mapping):
        return False
    direct_names = (
        "input_values",
        "initial_state",
        "expected_output",
        "expected_state",
        "expected_effects",
        "expected_errors",
        "input_field_mappings",
        "output_field_mappings",
        "state_field_mappings",
        "invariant_ids",
        "guarantee_ids",
        "protected_failure_ids",
    )
    if any(value.get(name) not in (None, "", (), [], {}) for name in direct_names):
        return True
    dimensions = value.get("dimensions")
    return isinstance(dimensions, Sequence) and any(
        isinstance(row, Mapping)
        and any(
            row.get(name) not in (None, "", (), [], {})
            for name in ("semantics", "semantic_rule_ids", "applicability_surface_ids")
        )
        for row in dimensions
    )


def _context_gap(
    code: str,
    *,
    message: str,
    owner_id: str = "",
    next_owner: str = "",
    evidence_refs: Iterable[str] = (),
    status: str = "unresolved",
    gap_id: str = "",
    category: str = "",
) -> dict[str, Any]:
    refs = sorted({str(item) for item in evidence_refs if str(item)})
    payload = {
        "code": str(code),
        "category": str(category or code),
        "status": str(status),
        "message": str(message),
        "owner_id": str(owner_id),
        "next_owner": str(next_owner),
        "evidence_refs": refs,
        "evidence_class": "unresolved",
    }
    payload["gap_id"] = gap_id or "task-gap:" + fingerprint_value(payload).split(":", 1)[-1]
    return payload


def _context_reason(edge_kind: str) -> str:
    return {
        "ancestor": "required parent/ancestor closure",
        "affected_sibling": "declared affected sibling invalidation",
        "child": "declared parent-to-child model dependency",
        "cross_boundary_support": "declared cross-boundary support relation",
        "delegates_to": "declared delegation dependency",
        "feedback": "declared feedback relation",
        "produces_for": "declared producer-to-consumer relation",
        "repair": "declared repair relation",
        "relation_consumer": "declared relation consumer dependency",
        "relation_producer": "declared relation producer dependency",
        "realization_member": "declared realization member dependency",
        "realization_owner": "declared realization owner dependency",
        "retry": "declared retry relation",
        "shared_resource": "declared shared resource dependency",
        "sibling": "declared common-parent sibling invalidation",
        "supports": "declared support relation",
    }.get(edge_kind, "declared typed topology relation")


def _context_snapshot(
    accepted_snapshot: Mapping[str, Any] | Any | None,
    *,
    accepted_snapshot_verified: bool,
    authority_root: str | Path | None = None,
    expected_index_fingerprint: str = "",
    expected_blueprint_fingerprint: str = "",
    authority_state: Any | None = None,
) -> dict[str, Any]:
    supplied = accepted_snapshot if accepted_snapshot is not None else {}
    as_of = str(
        _context_scalar(
            supplied,
            "as_of",
            "as_of_revision",
            "subject_revision",
            "accepted_revision",
            default="",
        )
        or ""
    )
    snapshot_id = str(
        _context_scalar(
            supplied,
            "snapshot_id",
            "snapshot_fingerprint",
            "evidence_fingerprint",
            "fingerprint",
            default="",
        )
        or ""
    )
    supplied_index_fingerprint = str(
        _context_scalar(
            supplied,
            "affected_index_fingerprint",
            "blueprint_index_fingerprint",
            "index_fingerprint",
            default="",
        )
        or ""
    )
    supplied_blueprint_fingerprint = str(
        _context_scalar(
            supplied,
            "blueprint_fingerprint",
            "target_blueprint_fingerprint",
            default="",
        )
        or ""
    )
    supplied_head = str(
        _context_scalar(
            supplied,
            "authority_head_fingerprint",
            "head_fingerprint",
            default="",
        )
        or ""
    )
    supplied_revision_set = str(
        _context_scalar(
            supplied,
            "accepted_revision_set_fingerprint",
            default="",
        )
        or ""
    )
    # ``verified`` and ``status=verified`` are descriptive caller input, not
    # evidence.  A current task map may claim accepted intent only when the
    # supplied identity is bound to the project's actual current authority
    # head, snapshot, and accepted revision.  The loader performs all native
    # content-address and transition checks; this projection only compares the
    # caller's explicit identity with that verified result.
    verification_reason = ""
    verified = False
    if authority_root is None:
        verification_reason = "authority root was not supplied"
    elif not as_of or not snapshot_id:
        verification_reason = "accepted snapshot identity is incomplete"
    elif expected_index_fingerprint and supplied_index_fingerprint != expected_index_fingerprint:
        verification_reason = (
            "accepted snapshot is not bound to the current affected index"
            if not supplied_index_fingerprint
            else "accepted snapshot affected index fingerprint is stale"
        )
    elif (
        expected_blueprint_fingerprint
        and supplied_blueprint_fingerprint
        and supplied_blueprint_fingerprint != expected_blueprint_fingerprint
    ):
        verification_reason = "accepted snapshot blueprint fingerprint is stale"
    elif not supplied_head or not supplied_revision_set:
        verification_reason = "accepted authority head identity is incomplete"
    else:
        try:
            if authority_state is not None:
                state = authority_state
            else:
                from .model_authority_store import load_current_model_authority_state

                state = load_current_model_authority_state(authority_root)
        except Exception as exc:  # authority errors remain an unresolved map gap
            verification_reason = f"current authority verification failed: {exc}"
        else:
            current_snapshot_id = str(state.snapshot.fingerprint)
            allowed_revisions = {
                str(state.snapshot.subject_revision),
                str(state.head.subject_revision),
                str(state.head.accepted_revision_set_fingerprint),
            }
            if state.accepted_revision is not None:
                allowed_revisions.add(str(state.accepted_revision.fingerprint))
            if snapshot_id != current_snapshot_id:
                verification_reason = "accepted snapshot fingerprint is not current"
            elif as_of not in allowed_revisions:
                verification_reason = "accepted snapshot revision is not current"
            elif supplied_head and supplied_head != str(state.head.fingerprint):
                verification_reason = "accepted authority head fingerprint is stale"
            elif (
                supplied_revision_set
                and supplied_revision_set
                != str(state.head.accepted_revision_set_fingerprint)
            ):
                verification_reason = "accepted revision-set fingerprint is stale"
            else:
                verified = True
                verification_reason = "accepted identity matches current authority"
    return {
        "status": "verified" if verified else "unavailable",
        "as_of": as_of if verified else "",
        "snapshot_id": snapshot_id if verified else "",
        "accepted_revision": as_of if verified else "",
        "affected_index_fingerprint": (
            expected_index_fingerprint if verified else ""
        ),
        "blueprint_fingerprint": (
            expected_blueprint_fingerprint if verified else ""
        ),
        "verification_reason": verification_reason,
        "claim_boundary": str(
            _context_scalar(supplied, "claim_boundary", default="") or ""
        )
        if verified
        else "Accepted intent/currentness is unavailable without an explicit verified as-of snapshot.",
    }


def _context_catalog_surfaces(
    surface_catalog: Mapping[str, Any] | Any | None,
) -> tuple[dict[str, Any], ...]:
    rows = _context_rows(
        surface_catalog,
        "surfaces",
        "implementation_surfaces",
        "members",
        "inventory",
    )
    result: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, Mapping):
            namespace = getattr(row, "__dict__", None)
            if not isinstance(namespace, dict):
                continue
            row = namespace
        surface_id = _context_id(row, "surface_id", "implementation_surface_id")
        if not surface_id:
            continue
        result.append(dict(row))
    return tuple(sorted(result, key=lambda row: _context_id(row, "surface_id", "implementation_surface_id")))


def _context_catalog_identity(
    surface_catalog: Mapping[str, Any] | Any | None,
) -> dict[str, str]:
    """Read catalog identity without treating caller metadata as proof."""

    if not isinstance(surface_catalog, Mapping):
        return {}
    nested = surface_catalog.get("_flowguard_catalog_identity")
    if not isinstance(nested, Mapping):
        nested = surface_catalog.get("catalog_identity")
    if not isinstance(nested, Mapping):
        nested = surface_catalog.get("identity")
    candidates: list[Mapping[str, Any]] = [surface_catalog]
    if isinstance(nested, Mapping):
        candidates.insert(0, nested)
    identity: dict[str, str] = {}
    aliases = {
        "affected_index_fingerprint": (
            "affected_index_fingerprint",
            "blueprint_index_fingerprint",
            "index_fingerprint",
        ),
        "blueprint_fingerprint": (
            "blueprint_fingerprint",
            "target_blueprint_fingerprint",
        ),
        "authority_snapshot_fingerprint": (
            "authority_snapshot_fingerprint",
            "snapshot_fingerprint",
            "snapshot_id",
        ),
        "inventory_shard_fingerprint": (
            "inventory_shard_fingerprint",
            "catalog_fingerprint",
        ),
        "surfaces_fingerprint": ("surfaces_fingerprint",),
    }
    for canonical, names in aliases.items():
        for candidate in candidates:
            for name in names:
                value = candidate.get(name)
                if value not in (None, ""):
                    identity[canonical] = str(value)
                    break
            if canonical in identity:
                break
    return identity


def _context_catalog_surfaces_fingerprint(
    rows: Sequence[Mapping[str, Any]],
) -> str:
    return fingerprint_value(
        {
            "surfaces": [
                _context_safe(dict(row))
                for row in sorted(
                    rows,
                    key=lambda value: _context_id(
                        value, "surface_id", "implementation_surface_id"
                    ),
                )
            ]
        }
    )


def _context_surface_rows(
    read_result: AffectedBlueprintReadResult,
    *,
    surface_catalog: Mapping[str, Any] | Any | None,
    changed_paths: Iterable[str],
    expected_index_fingerprint: str = "",
    expected_blueprint_fingerprint: str = "",
    expected_snapshot_fingerprint: str = "",
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    objects = _context_objects(read_result)
    blocks = _context_behavior_blocks(objects)
    owner_by_surface: dict[str, set[str]] = {}
    block_by_surface: dict[str, list[tuple[str, Any]]] = {}
    for block_id, block in blocks:
        surface_id = _context_id(block, "implementation_surface_id")
        if not surface_id:
            continue
        block_by_surface.setdefault(surface_id, []).append((block_id, block))
        owner_id = _context_id(block, "owner_id", "behavior_owner_id")
        if owner_id:
            owner_by_surface.setdefault(surface_id, set()).add(owner_id)

    catalog_rows = list(_context_catalog_surfaces(surface_catalog))
    catalog_gaps: list[dict[str, Any]] = []
    catalog_identity = _context_catalog_identity(surface_catalog)
    if surface_catalog is not None:
        expected_catalog_identity = {
            "affected_index_fingerprint": expected_index_fingerprint,
            "blueprint_fingerprint": expected_blueprint_fingerprint,
            "authority_snapshot_fingerprint": expected_snapshot_fingerprint,
        }
        if not catalog_identity:
            catalog_gaps.append(
                _context_gap(
                    "surface_catalog_identity_unavailable",
                    message=(
                        "surface catalog has no independently bound index, blueprint, "
                        "or authority identity; it is display-only"
                    ),
                    next_owner="implementation-inventory-owner",
                    evidence_refs=tuple(
                        _context_id(row, "surface_id", "implementation_surface_id")
                        for row in catalog_rows
                    ),
                )
            )
        for field_name, expected in expected_catalog_identity.items():
            supplied = catalog_identity.get(field_name, "")
            if expected and supplied and supplied != expected:
                catalog_gaps.append(
                    _context_gap(
                        "surface_catalog_identity_mismatch",
                        message=(
                            f"surface catalog {field_name} does not match the current "
                            f"affected closure: supplied={supplied or '<missing>'}, "
                            f"expected={expected}"
                        ),
                        next_owner="implementation-inventory-owner",
                        evidence_refs=(field_name, supplied, expected),
                        status="blocked",
                    )
                )
            elif expected and catalog_identity and not supplied:
                catalog_gaps.append(
                    _context_gap(
                        "surface_catalog_identity_unavailable",
                        message=(
                            f"surface catalog identity is missing required field: {field_name}"
                        ),
                        next_owner="implementation-inventory-owner",
                        evidence_refs=(field_name,),
                    )
                )
        supplied_surfaces_fingerprint = catalog_identity.get(
            "surfaces_fingerprint", ""
        )
        if supplied_surfaces_fingerprint and supplied_surfaces_fingerprint != _context_catalog_surfaces_fingerprint(catalog_rows):
            catalog_gaps.append(
                _context_gap(
                    "surface_catalog_identity_mismatch",
                    message="surface catalog surface rows do not match their declared fingerprint",
                    next_owner="implementation-inventory-owner",
                    evidence_refs=(supplied_surfaces_fingerprint,),
                    status="blocked",
                )
            )

    # Canonical surface facts from the loaded closure win.  A caller catalog
    # may fill missing coordinates, but it cannot replace a current owner,
    # path, symbol, or source fingerprint with a modified value.
    canonical_by_surface: dict[str, dict[str, Any]] = {}
    for object_id, value in objects.items():
        if not isinstance(value, Mapping):
            continue
        kind = str(value.get("kind", ""))
        if kind in {
            "implementation_surface",
            "implementation_surface_record",
            "surface",
        }:
            surface_id = _context_id(value, "surface_id", "implementation_surface_id")
            if surface_id:
                canonical_by_surface.setdefault(surface_id, dict(value))
        elif kind == "implementation_surface_index":
            surface_id = _context_id(value, "implementation_surface_id")
            if surface_id:
                canonical_by_surface.setdefault(surface_id, dict(value))
    for surface_id, rows_for_surface in block_by_surface.items():
        canonical = canonical_by_surface.setdefault(surface_id, {"surface_id": surface_id})
        owner_ids = sorted(owner_by_surface.get(surface_id, ()))
        if len(owner_ids) == 1:
            canonical.setdefault("owner_id", owner_ids[0])
        for _block_id, block in rows_for_surface:
            source_fingerprint = _context_source_fingerprint(block)
            if source_fingerprint:
                canonical.setdefault("source_fingerprint", source_fingerprint)
                break

    by_surface: dict[str, dict[str, Any]] = {
        surface_id: dict(row) for surface_id, row in canonical_by_surface.items()
    }
    identity_fields = (
        "path",
        "symbol",
        "line_start",
        "line_end",
        "owner_id",
        "behavior_owner_id",
        "source_fingerprint",
        "content_fingerprint",
        "structure_fingerprint",
    )
    catalog_identity_blocked = any(
        gap.get("code") == "surface_catalog_identity_mismatch"
        for gap in catalog_gaps
    )
    catalog_rows_for_merge = () if catalog_identity_blocked else catalog_rows
    for catalog_row in catalog_rows_for_merge:
        surface_id = _context_id(
            catalog_row, "surface_id", "implementation_surface_id"
        )
        if not surface_id:
            continue
        canonical = by_surface.get(surface_id)
        if canonical is None:
            by_surface[surface_id] = dict(catalog_row)
            continue
        conflicting_fields: list[str] = []
        for field_name in identity_fields:
            canonical_value = _context_scalar(canonical, field_name, default="")
            catalog_value = _context_scalar(catalog_row, field_name, default="")
            if canonical_value not in (None, "") and catalog_value not in (None, ""):
                if str(canonical_value) != str(catalog_value):
                    conflicting_fields.append(field_name)
        if conflicting_fields:
            catalog_gaps.append(
                _context_gap(
                    "surface_catalog_identity_mismatch",
                    message=(
                        f"surface catalog row {surface_id} disagrees with the loaded "
                        f"canonical surface identity: {', '.join(conflicting_fields)}"
                    ),
                    owner_id=surface_id,
                    next_owner="implementation-inventory-owner",
                    evidence_refs=(surface_id, *conflicting_fields),
                    status="blocked",
                )
            )
            continue
        merged = dict(canonical)
        for key, value in catalog_row.items():
            if key not in merged or merged[key] in (None, "", (), [], {}):
                merged[key] = value
        by_surface[surface_id] = merged

    changed: list[str] = []
    invalid_changes: list[dict[str, Any]] = []
    for raw_path in (changed_paths or ()):
        raw = str(raw_path).strip()
        if not raw:
            continue
        normalized = raw.replace("\\", "/")
        candidate = PurePosixPath(normalized)
        if candidate.is_absolute() or ".." in candidate.parts:
            invalid_changes.append(
                _context_gap(
                    "invalid_changed_path",
                    message=f"changed path is not repository-relative: {raw}",
                    next_owner="change-admission",
                )
            )
            continue
        changed.append(candidate.as_posix())

    selected_ids: set[str] = set()
    if changed:
        path_matches: dict[str, list[str]] = {}
        for surface_id, row in by_surface.items():
            path, _ = _context_path(row)
            if path:
                path_matches.setdefault(path, []).append(surface_id)
        for path in sorted(set(changed)):
            matches = sorted(path_matches.get(path, ()))
            if not matches:
                invalid_changes.append(
                    _context_gap(
                        "unknown_change_point",
                        message=f"changed path does not resolve to a current implementation surface: {path}",
                        next_owner="implementation-inventory-owner",
                    )
                )
            selected_ids.update(matches)
    else:
        selected_ids.update(by_surface)
        selected_ids.update(block_by_surface)

    rows: list[dict[str, Any]] = []
    gaps = [*catalog_gaps, *invalid_changes]
    # A block is itself an exact affected change point even when the normalized
    # surface index has no coordinate payload.  Emit the row with explicit
    # missing coordinates and a gap instead of guessing a path or symbol.
    for surface_id in sorted(selected_ids):
        surface = by_surface.get(surface_id, {"surface_id": surface_id})
        owner_ids = set(owner_by_surface.get(surface_id, set()))
        declared_surface_owner = _context_id(
            surface, "owner_id", "behavior_owner_id"
        )
        if declared_surface_owner:
            owner_ids.add(declared_surface_owner)
        owner_id = next(iter(owner_ids)) if len(owner_ids) == 1 else ""
        row = _context_surface_payload(
            surface_id,
            surface,
            owner_id=owner_id,
            source_ref=surface_id,
        )
        if not row["source_fingerprint"]:
            for _block_id, block in block_by_surface.get(surface_id, ()):
                row["source_fingerprint"] = _context_source_fingerprint(block)
                if row["source_fingerprint"]:
                    break
        if len(owner_ids) != 1:
            gaps.append(
                _context_gap(
                    "owner_ambiguous" if owner_ids else "owner_unknown",
                    message=(
                        f"surface {surface_id} maps to multiple owners: {sorted(owner_ids)}"
                        if owner_ids
                        else f"surface {surface_id} has no exact behavior owner"
                    ),
                    owner_id=surface_id,
                    next_owner="behavior-owner-resolution",
                    evidence_refs=(surface_id,),
                )
            )
        if not row["path"] or not row["symbol"] or not row["source_fingerprint"]:
            gaps.append(
                _context_gap(
                    "surface_coordinates_unresolved",
                    message=f"surface {surface_id} lacks complete path, symbol, or source fingerprint coordinates",
                    owner_id=owner_id,
                    next_owner="implementation-inventory-owner",
                    evidence_refs=(surface_id,),
                )
            )
        if row.get("path_gap"):
            gaps.append(
                _context_gap(
                    "invalid_surface_path",
                    message=f"surface {surface_id} contains an invalid repository path",
                    owner_id=owner_id,
                    next_owner="implementation-inventory-owner",
                    evidence_refs=(surface_id,),
                )
            )
        rows.append(row)
    return rows, gaps


def _context_intent_rows(
    read_result: AffectedBlueprintReadResult,
    blocks: Sequence[tuple[str, Any]],
    *,
    snapshot: Mapping[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    objects = _context_objects(read_result)
    rows: list[dict[str, Any]] = []
    gaps: list[dict[str, Any]] = []
    linked_ids: set[str] = set()
    for _block_id, block in blocks:
        linked_ids.update(
            _context_related_ids(
                block,
                "intent_contribution_ids",
                "intent_ids",
                "intent_id",
            )
        )
    candidates: list[tuple[str, Any]] = []
    for object_id, value in objects.items():
        kind = str(value.get("kind", "")) if isinstance(value, Mapping) else ""
        contribution_id = _context_id(value, "contribution_id", "intent_id", "commitment_id")
        if object_id in linked_ids or contribution_id in linked_ids or kind in {
            "intent_contribution",
            "project_intent_contribution",
        }:
            if contribution_id or object_id in linked_ids:
                candidates.append((object_id, value))
    for object_id, value in sorted(candidates):
        intent_id = _context_id(value, "contribution_id", "intent_id") or object_id
        disposition = str(_context_scalar(value, "disposition", "status", default="") or "")
        source_ref = {
            key: str(_context_scalar(value, key, default="") or "")
            for key in ("source_kind", "source_id", "source_owner_id", "source_fingerprint")
            if _context_scalar(value, key, default="") not in (None, "")
        }
        expectation_id = _context_id(value, "expectation_id")
        expectation_fp = str(
            _context_scalar(value, "expectation_fingerprint", default="") or ""
        )
        expectation: dict[str, Any] = {
            "expectation_id": expectation_id,
            "expectation_fingerprint": expectation_fp,
        }
        for key in ("expectation", "expected", "rationale"):
            supplied = _context_stored(value, key, _MISSING)
            if supplied is not _MISSING:
                expectation[key] = _context_safe(supplied)
        accepted = disposition in {"accepted", "current", "approved"} or _context_bool(
            value, "accepted", default=False
        )
        is_verified = snapshot.get("status") == "verified"
        row = {
            "intent_id": intent_id,
            "commitment_id": _context_id(value, "commitment_id"),
            "source_ref": source_ref,
            "accepted_revision": str(snapshot.get("accepted_revision", ""))
            if is_verified and accepted
            else "",
            "expectation": expectation,
            "disposition": disposition,
            "accepted": bool(accepted and is_verified),
            "claim_boundary": str(snapshot.get("claim_boundary", "")),
            "evidence_refs": sorted(
                {
                    ref
                    for ref in (
                        object_id,
                        str(_context_scalar(value, "source_fingerprint", default="") or ""),
                        str(_context_scalar(value, "expectation_fingerprint", default="") or ""),
                    )
                    if ref
                }
            ),
            "evidence_class": "accepted_contract"
            if accepted and is_verified
            else "unresolved",
        }
        rows.append(row)
        if not accepted:
            gaps.append(
                _context_gap(
                    "intent_not_accepted",
                    message=f"intent contribution {intent_id} is not accepted",
                    next_owner="intent-authority-owner",
                    evidence_refs=(object_id,),
                )
            )
    if not rows:
        gaps.append(
            _context_gap(
                "accepted_intent_unresolved",
                message="affected closure has no linked accepted intent contribution",
                next_owner="intent-authority-owner",
            )
        )
    if snapshot.get("status") != "verified":
        gaps.append(
            _context_gap(
                "accepted_snapshot_unavailable",
                message="no explicit independently verified as-of snapshot was supplied; accepted currentness is not claimed",
                next_owner="model-authority-owner",
                evidence_refs=tuple(
                    str(item)
                    for item in (
                        snapshot.get("as_of", ""),
                        snapshot.get("snapshot_id", ""),
                    )
                    if item
                ),
            )
        )
    return rows, gaps


def _context_case(value: Any, object_id: str) -> dict[str, Any]:
    return {
        "case_id": _context_id(value, "case_id") or object_id,
        "behavior_block_id": _context_id(value, "behavior_block_id"),
        "case_kind": str(_context_scalar(value, "case_kind", default="") or ""),
        "input_values": _context_safe(_context_scalar(value, "input_values", default={})),
        "initial_state": _context_safe(_context_scalar(value, "initial_state", default={})),
        "expected_output": _context_safe(
            _context_scalar(value, "expected_output", default={})
        ),
        "expected_state": _context_safe(
            _context_scalar(value, "expected_state", default={})
        ),
        "expected_effects": _context_safe(
            _context_scalar(value, "expected_effects", default=[])
        ),
        "expected_errors": _context_safe(
            _context_scalar(value, "expected_errors", default=[])
        ),
        "oracle_id": _context_id(value, "oracle_id"),
        "case_evidence_id": _context_id(value, "case_evidence_id"),
        "case_evidence_fingerprint": str(
            _context_scalar(value, "case_evidence_fingerprint", default="") or ""
        ),
        "protected_failure_ids": _context_strings(value, "protected_failure_ids"),
        "source_ref": object_id,
        "evidence_class": "accepted_contract",
    }


def _context_must_preserve_rows(
    read_result: AffectedBlueprintReadResult,
    blocks: Sequence[tuple[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    objects = _context_objects(read_result)
    rows: list[dict[str, Any]] = []
    gaps: list[dict[str, Any]] = []
    for block_id, block in blocks:
        related_ids = set(
            _context_related_ids(
                block,
                "portable_binding_ids",
                "semantic_spec_ids",
                "oracle_ids",
                "case_ids",
                "behavior_case_ids",
                "coverage_ids",
            )
        )
        related_ids.update(
            _context_related_ids(
                block,
                "owner_id",
                "owner_contract_id",
                "model_element_id",
            )
        )
        semantic_ids = set(_context_related_ids(block, "semantic_spec_ids"))
        oracle_ids = set(_context_related_ids(block, "oracle_ids"))
        related = [
            (object_id, value)
            for object_id, value in objects.items()
            if object_id in related_ids
            or (
                isinstance(value, Mapping)
                and _context_id(value, "behavior_block_id") == block_id
            )
        ]
        dimensions_raw = _context_stored(block, "dimensions", ()) or ()
        dimensions: list[Any] = []
        if isinstance(dimensions_raw, Mapping):
            dimensions = [
                {"dimension": str(key), **(_context_safe(value) if isinstance(value, Mapping) else {"semantics": _context_safe(value)})}
                for key, value in dimensions_raw.items()
            ]
        elif isinstance(dimensions_raw, Sequence) and not isinstance(
            dimensions_raw, (str, bytes, bytearray)
        ):
            dimensions = [_context_safe(item) for item in dimensions_raw]
        by_dimension: dict[str, Any] = {}
        for dimension in dimensions:
            if isinstance(dimension, Mapping):
                key = str(dimension.get("dimension", ""))
                if key:
                    by_dimension[key] = dimension

        def direct_or_dimension(*names: str, dimension: str) -> Any:
            supplied = _context_scalar(block, *names, default=_MISSING)
            if supplied is not _MISSING:
                return _context_safe(supplied)
            return by_dimension.get(dimension, {})

        cases = [
            _context_case(value, object_id)
            for object_id, value in sorted(related)
            if isinstance(value, Mapping)
            and value.get("kind") in {"behavior_case_contract", "behavior_case"}
        ]
        bindings = [
            _context_safe(value)
            for _object_id, value in sorted(related)
            if isinstance(value, Mapping)
            and value.get("kind") == "portable_behavior_binding"
        ]
        oracles = [
            _context_safe(value)
            for _object_id, value in sorted(related)
            if isinstance(value, Mapping)
            and (
                value.get("kind") in {"oracle", "oracle_reference"}
                or _object_id in oracle_ids
                or bool(value.get("oracle_id"))
            )
        ]
        semantic_specs = [
            _context_safe(value)
            for _object_id, value in sorted(related)
            if isinstance(value, Mapping)
            and (
                value.get("kind") in {"semantic_spec", "semantic_spec_reference"}
                or _object_id in semantic_ids
                or bool(value.get("semantic_spec_id"))
            )
        ]
        input_contract = direct_or_dimension(
            "inputs", "input_contract", "input_values", dimension="input"
        )
        state_contract = direct_or_dimension(
            "state", "state_contract", "initial_state", dimension="state"
        )
        output_contract = direct_or_dimension(
            "outputs", "output_contract", "expected_output", dimension="output"
        )
        effect_contract = direct_or_dimension(
            "effects", "effect_contract", "side_effects", dimension="effect"
        )
        error_contract = direct_or_dimension(
            "errors", "error_contract", "expected_errors", dimension="error"
        )
        completion_contract = direct_or_dimension(
            "completion", "completion_contract", dimension="completion"
        )
        invariant_ids: set[str] = set(_context_strings(block, "invariant_ids"))
        protected_failures = set(
            _context_strings(block, "protected_failure_ids")
        )
        for item in related:
            value = item[1]
            invariant_ids.update(_context_strings(value, "invariant_ids"))
            protected_failures.update(
                _context_strings(value, "protected_failure_ids")
            )
        source_refs = sorted(
            {
                ref
                for ref in (
                    block_id,
                    _context_id(block, "model_element_id"),
                    _context_id(block, "owner_id"),
                    _context_id(block, "owner_contract_id"),
                    _context_source_fingerprint(block),
                    *[object_id for object_id, _value in related],
                )
                if ref
            }
        )
        row = {
            "behavior_block_id": block_id,
            "owner_id": _context_id(block, "owner_id", "behavior_owner_id"),
            "owner_contract_id": _context_id(block, "owner_contract_id"),
            "model_element_id": _context_id(block, "model_element_id"),
            "source_fingerprint": _context_source_fingerprint(block),
            "function_relation": str(
                _context_scalar(block, "function_relation", default="") or ""
            ),
            "inputs": input_contract,
            "input_contract": input_contract,
            "external_inputs": input_contract,
            "state": state_contract,
            "state_contract": state_contract,
            "state_reads": _context_safe(
                _context_scalar(block, "state_reads", default=[])
            ),
            "state_writes": _context_safe(
                _context_scalar(block, "state_writes", default=[])
            ),
            "outputs": output_contract,
            "output_contract": output_contract,
            "external_outputs": output_contract,
            "effects": effect_contract,
            "effect_contract": effect_contract,
            "side_effects": effect_contract,
            "errors": error_contract,
            "error_contract": error_contract,
            "error_paths": error_contract,
            "completion": completion_contract,
            "dimensions": dimensions,
            "invariant_ids": sorted(invariant_ids),
            "protected_failure_ids": sorted(protected_failures),
            "portable_bindings": bindings,
            "semantic_specs": semantic_specs,
            "oracle_members": oracles,
            "case_contracts": cases,
            "source_refs": source_refs,
            "evidence_class": "accepted_contract",
        }
        serialized = _context_safe(block)
        has_placeholder = _context_placeholder(serialized)
        has_structured = _context_has_structured_contract(block) or bool(cases)
        if not has_structured or has_placeholder:
            row["evidence_class"] = "unresolved"
            gaps.append(
                _context_gap(
                    "contract_details_unresolved",
                    message=(
                        f"behavior block {block_id} has only a template/summary or no structured contract details"
                        if has_placeholder
                        else f"behavior block {block_id} has no structured input/state/output/effect contract"
                    ),
                    owner_id=_context_id(block, "owner_id", "behavior_owner_id"),
                    next_owner="behavior-contract-owner",
                    evidence_refs=source_refs,
                )
            )
        rows.append(row)
    if not rows:
        gaps.append(
            _context_gap(
                "must_preserve_unresolved",
                message="affected closure contains no behavior block contract",
                next_owner="behavior-contract-owner",
            )
        )
    return rows, gaps


def _context_impact_rows(
    read_result: AffectedBlueprintReadResult,
    index: AffectedBlueprintIndex,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    affected = set(read_result.affected_ids)
    seeds = tuple(read_result.requested_seed_ids)
    traversed_identities = set(read_result.traversed_topology_edge_identities)
    # The reader already performed the context-sensitive closure walk.  Use
    # the exact edge-to-path records from that walk; rebuilding BFS here would
    # lose the child-descent state and could reopen parent-to-sibling edges
    # that were deliberately not traversed for a child seed.
    edges = tuple(
        edge
        for edge in index.topology_invalidation_edges
        if edge.identity in traversed_identities
    )
    paths_by_edge: dict[
        tuple[str, str, str, str],
        tuple[str, tuple[str, ...], tuple[tuple[str, str, str, str], ...]],
    ] = {}
    for seed_id, node_ids, edge_identities in read_result.traversed_topology_paths:
        for offset, edge_identity in enumerate(edge_identities):
            if edge_identity not in traversed_identities:
                continue
            candidate = (
                str(seed_id),
                tuple(str(item) for item in node_ids[: offset + 2]),
                tuple(edge_identities[: offset + 1]),
            )
            current = paths_by_edge.get(edge_identity)
            if current is None or (
                len(candidate[2]),
                candidate[2],
                candidate[0],
                candidate[1],
            ) < (
                len(current[2]),
                current[2],
                current[0],
                current[1],
            ):
                paths_by_edge[edge_identity] = candidate
    rows: list[dict[str, Any]] = []
    unresolved_edges: list[AffectedTopologyInvalidationEdge] = []
    for edge in edges:
        if edge.source_id not in affected and edge.target_id not in affected:
            continue
        selected = paths_by_edge.get(edge.identity)
        if selected is None:
            # A legacy/in-memory result may contain the edge identity but not
            # the new path record. Keep the typed edge visible, but do not
            # claim a seed-to-target explanation for it.
            path = (edge.source_id, edge.target_id)
            seed_id = ""
            unresolved_edges.append(edge)
        else:
            seed_id, path, _edge_path = selected
            if not path or path[-1] != edge.target_id:
                path = (*path, edge.target_id)
        path_id = "task-impact-path:" + fingerprint_value(
            {
                "path": list(path),
                "edge_kind": edge.edge_kind,
                "via_node_id": edge.via_node_id,
                "evidence_object_ids": list(edge.evidence_object_ids),
            }
        ).split(":", 1)[-1]
        rows.append(
            {
                "path_id": path_id,
                "seed_id": seed_id,
                "path": list(path),
                "source_id": edge.source_id,
                "target_id": edge.target_id,
                "edge_kind": edge.edge_kind,
                "via": edge.via_node_id,
                "via_node_id": edge.via_node_id,
                "evidence_refs": list(edge.evidence_object_ids),
                "reason": _context_reason(edge.edge_kind),
                "evidence_class": "observed_structure",
            }
        )
    rows.sort(key=lambda row: (row["path_id"], row["source_id"], row["target_id"]))
    gaps: list[dict[str, Any]] = []
    if not rows or unresolved_edges:
        gaps.append(
            _context_gap(
                "impact_path_unresolved",
                message=(
                    "affected closure has no declared typed topology edge for the selected seed"
                    if not rows
                    else "one or more affected topology edges cannot be traced back to a selected seed"
                ),
                next_owner="model-topology-owner",
                evidence_refs=(
                    *seeds,
                    *(evidence for edge in unresolved_edges for evidence in edge.evidence_object_ids),
                ),
            )
        )
    return rows, gaps


def _context_execution_disposition(value: Any) -> str:
    raw = str(_context_scalar(value, "disposition", "status", default="") or "").lower()
    if raw in {"pass", "passed", "reuse", "reused", "current"}:
        return "reuse"
    if raw in {"execute", "pending", "planned", "ready"}:
        return "execute"
    if raw in {"blocked", "fail", "failed", "error", "stale"}:
        return "blocked"
    return "not_run"


def _context_validation_rows(
    read_result: AffectedBlueprintReadResult,
    blocks: Sequence[tuple[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    objects = _context_objects(read_result)
    coverage_rows = [
        (object_id, value)
        for object_id, value in objects.items()
        if isinstance(value, Mapping) and value.get("kind") == "behavior_coverage_edge"
    ]
    execution_rows = [
        (object_id, value)
        for object_id, value in objects.items()
        if isinstance(value, Mapping)
        and value.get("kind")
        in {"coverage_execution_evidence", "behavior_coverage_execution"}
    ]
    executions_by_coverage: dict[str, list[tuple[str, Any]]] = {}
    for object_id, value in execution_rows:
        coverage_id = _context_id(value, "coverage_id")
        if coverage_id:
            executions_by_coverage.setdefault(coverage_id, []).append((object_id, value))
    receipts = {
        object_id: value
        for object_id, value in objects.items()
        if isinstance(value, Mapping) and value.get("kind") in {
            "terminal_execution_receipt",
            "execution_receipt",
        }
    }
    rows: list[dict[str, Any]] = []
    gaps: list[dict[str, Any]] = []
    for object_id, value in sorted(coverage_rows):
        coverage_id = _context_id(value, "coverage_id") or object_id
        block_id = _context_id(value, "behavior_block_id")
        case_id = _context_id(value, "case_id")
        case_value = objects.get(case_id, {})
        test_node_id = _context_id(value, "test_node_id")
        test_value = objects.get(test_node_id, {})
        execution = sorted(executions_by_coverage.get(coverage_id, ()))
        execution_id, execution_value = execution[0] if execution else ("", {})
        disposition = _context_execution_disposition(execution_value) if execution else "not_run"
        receipt_id = _context_id(execution_value, "receipt_id")
        receipt_fp = str(
            _context_scalar(
                execution_value,
                "receipt_fingerprint",
                "execution_fingerprint",
                default="",
            )
            or ""
        )
        if disposition == "reuse" and receipt_id:
            receipt = receipts.get(receipt_id)
            if receipt is None or (
                receipt_fp
                and str(_context_scalar(receipt, "fingerprint", default="") or "")
                not in {receipt_fp, ""}
            ):
                disposition = "blocked"
                gaps.append(
                    _context_gap(
                        "validation_receipt_mismatch",
                        message=f"coverage {coverage_id} has no matching terminal receipt",
                        owner_id=_context_id(value, "behavior_owner_id", "owner_id"),
                        next_owner="native-test-owner",
                        evidence_refs=(coverage_id, receipt_id),
                        status="blocked",
                    )
                )
        if not execution:
            gaps.append(
                _context_gap(
                    "validation_not_run",
                    message=f"coverage {coverage_id} has no exact execution evidence",
                    owner_id=_context_id(value, "behavior_owner_id", "owner_id"),
                    next_owner=_context_id(test_value, "owner_id") or "native-test-owner",
                    evidence_refs=(coverage_id, test_node_id, case_id),
                )
            )
        if not test_node_id or not isinstance(test_value, Mapping):
            gaps.append(
                _context_gap(
                    "validation_owner_unresolved",
                    message=f"coverage {coverage_id} has no exact test node selector",
                    owner_id=_context_id(value, "behavior_owner_id", "owner_id"),
                    next_owner="test-inventory-owner",
                    evidence_refs=(coverage_id,),
                )
            )
        if not case_id or not isinstance(case_value, Mapping):
            gaps.append(
                _context_gap(
                    "validation_case_unresolved",
                    message=f"coverage {coverage_id} has no exact behavior case contract",
                    owner_id=_context_id(value, "behavior_owner_id", "owner_id"),
                    next_owner="behavior-case-owner",
                    evidence_refs=(coverage_id,),
                )
            )
        row = {
            "coverage_id": coverage_id,
            "behavior_block_id": block_id,
            "owner_id": _context_id(value, "behavior_owner_id", "owner_id"),
            "model_obligation_id": _context_id(value, "model_obligation_id"),
            "implementation_surface_id": _context_id(value, "implementation_surface_id"),
            "test_node_id": test_node_id,
            "selector": str(
                _context_scalar(test_value, "pytest_nodeid", "selector", default="") or ""
            ),
            "test_path": str(_context_scalar(test_value, "path", default="") or ""),
            "case_id": case_id,
            "case_kind": str(_context_scalar(case_value, "case_kind", default="") or ""),
            "case_contract": _context_case(case_value, case_id)
            if isinstance(case_value, Mapping)
            else {},
            "oracle_id": _context_id(value, "oracle_id") or _context_id(case_value, "oracle_id"),
            "oracle_member_id": _context_id(value, "oracle_member_id"),
            "covered_dimensions": _context_strings(value, "covered_dimensions"),
            "execution_owner_id": _context_id(execution_value, "execution_owner_id"),
            "disposition": disposition,
            "receipt_id": receipt_id,
            "receipt_fingerprint": receipt_fp,
            "execution_evidence_id": execution_id,
            "reason": str(_context_scalar(execution_value, "reason", default="") or "")
            or ("no exact execution evidence" if not execution else ""),
            "impact_reason": "coverage edge binds model obligation, implementation surface, test selector, case, and oracle",
            "evidence_refs": sorted(
                {
                    ref
                    for ref in (object_id, coverage_id, execution_id, receipt_id, test_node_id, case_id)
                    if ref
                }
            ),
            "evidence_class": "executed_evidence"
            if disposition == "reuse" and receipt_id
            else "unresolved",
        }
        rows.append(row)

    # A closure can carry a test node without a coverage edge.  Keep that
    # omission visible as a not-run validation row rather than declaring a
    # test owner complete from inventory presence alone.
    covered_test_ids = {row["test_node_id"] for row in rows if row["test_node_id"]}
    for object_id, value in sorted(objects.items()):
        if not isinstance(value, Mapping) or value.get("kind") != "test_node":
            continue
        if object_id in covered_test_ids:
            continue
        rows.append(
            {
                "coverage_id": "",
                "behavior_block_id": "",
                "owner_id": _context_id(value, "owner_id"),
                "model_obligation_id": "",
                "implementation_surface_id": "",
                "test_node_id": object_id,
                "selector": str(_context_scalar(value, "pytest_nodeid", default="") or ""),
                "test_path": str(_context_scalar(value, "path", default="") or ""),
                "case_id": "",
                "case_kind": "",
                "case_contract": {},
                "oracle_id": "",
                "oracle_member_id": "",
                "covered_dimensions": [],
                "execution_owner_id": "",
                "disposition": "not_run",
                "receipt_id": "",
                "receipt_fingerprint": "",
                "execution_evidence_id": "",
                "reason": "test node is not bound by a coverage edge",
                "impact_reason": "no declared model-to-test coverage edge",
                "evidence_refs": [object_id],
                "evidence_class": "unresolved",
            }
        )
        gaps.append(
            _context_gap(
                "validation_coverage_unresolved",
                message=f"test node {object_id} is not bound by a behavior coverage edge",
                owner_id=_context_id(value, "owner_id"),
                next_owner="model-test-alignment-owner",
                evidence_refs=(object_id,),
            )
        )
    if not rows and blocks:
        gaps.append(
            _context_gap(
                "validation_unresolved",
                message="affected behavior blocks have no coverage/test validation rows",
                next_owner="model-test-alignment-owner",
            )
        )
    rows.sort(key=lambda row: (str(row.get("coverage_id", "")), str(row.get("test_node_id", ""))))
    return rows, gaps


def build_affected_task_context(
    read_result: AffectedBlueprintReadResult,
    index: AffectedBlueprintIndex,
    *,
    target: Mapping[str, Any] | None = None,
    legacy_gaps: Sequence[BlueprintGapRef] = (),
    status: str = "",
    task_summary: str = "",
    changed_paths: Iterable[str] = (),
    surface_catalog: Mapping[str, Any] | Any | None = None,
    accepted_snapshot: Mapping[str, Any] | Any | None = None,
    accepted_snapshot_verified: bool = False,
    authority_root: str | Path | None = None,
    authority_state: Any | None = None,
) -> dict[str, Any]:
    """Build the six-group AI work map from one already loaded closure.

    This function is deliberately a pure projection.  It reads only
    ``read_result`` and optional, caller-supplied materialized catalogs; it
    never scans the repository, launches a producer, or treats source calls as
    semantic impact edges.
    """

    target = target if isinstance(target, Mapping) else {}
    objects = _context_objects(read_result)
    blocks = _context_behavior_blocks(objects)
    snapshot = _context_snapshot(
        accepted_snapshot,
        accepted_snapshot_verified=accepted_snapshot_verified,
        authority_root=authority_root,
        expected_index_fingerprint=index.fingerprint,
        expected_blueprint_fingerprint=index.blueprint_fingerprint,
        authority_state=authority_state,
    )
    selected, selected_gaps = _context_surface_rows(
        read_result,
        surface_catalog=surface_catalog,
        changed_paths=changed_paths,
        expected_index_fingerprint=index.fingerprint,
        expected_blueprint_fingerprint=index.blueprint_fingerprint,
        expected_snapshot_fingerprint=str(snapshot.get("snapshot_id", "") or ""),
    )
    intents, intent_gaps = _context_intent_rows(
        read_result,
        blocks,
        snapshot=snapshot,
    )
    preserve, preserve_gaps = _context_must_preserve_rows(read_result, blocks)
    impacts, impact_gaps = _context_impact_rows(read_result, index)
    validation, validation_gaps = _context_validation_rows(read_result, blocks)

    gaps: list[dict[str, Any]] = []
    for gap in legacy_gaps:
        gap_id = str(_context_stored(gap, "gap_id", "") or "")
        payload = _context_gap(
            "blueprint_gap",
            message=str(_context_stored(gap, "message", "") or ""),
            owner_id=str(_context_stored(gap, "owner_id", "") or ""),
            evidence_refs=(
                str(_context_stored(gap, "evidence_ref", "") or ""),
                str(_context_stored(gap, "object_id", "") or ""),
            ),
            status=str(_context_stored(gap, "status", "unresolved") or "unresolved"),
            gap_id=gap_id,
            category=str(_context_stored(gap, "layer", "") or "blueprint_gap"),
        )
        payload["object_kind"] = str(_context_stored(gap, "object_kind", "") or "")
        payload["object_id"] = str(_context_stored(gap, "object_id", "") or "")
        payload["expected_fingerprint"] = str(
            _context_stored(gap, "expected_fingerprint", "") or ""
        )
        payload["observed_fingerprint"] = str(
            _context_stored(gap, "observed_fingerprint", "") or ""
        )
        gaps.append(payload)
    gaps.extend(selected_gaps)
    gaps.extend(intent_gaps)
    gaps.extend(preserve_gaps)
    gaps.extend(impact_gaps)
    gaps.extend(validation_gaps)
    # Stable de-duplication is important because a missing leaf can be
    # reported by both the contract and validation projections.
    unique_gaps: dict[str, dict[str, Any]] = {}
    for gap in gaps:
        gap_id = str(gap.get("gap_id", ""))
        if not gap_id:
            gap_id = "task-gap:" + fingerprint_value(gap).split(":", 1)[-1]
            gap["gap_id"] = gap_id
        existing = unique_gaps.get(gap_id)
        if existing is None:
            unique_gaps[gap_id] = gap
        else:
            refs = sorted(
                set(existing.get("evidence_refs", ()))
                | set(gap.get("evidence_refs", ()))
            )
            existing["evidence_refs"] = refs
            if existing.get("status") != "blocked" and gap.get("status") == "blocked":
                existing["status"] = "blocked"
    ordered_gaps = [unique_gaps[key] for key in sorted(unique_gaps)]
    boundary_refs = {
        "observed_structure": sorted(
            {
                ref
                for row in (*selected, *impacts)
                for ref in (
                    row.get("source_ref", ""),
                    row.get("source_fingerprint", ""),
                    row.get("path_id", ""),
                    *row.get("evidence_refs", ()),
                )
                if ref
            }
        ),
        "accepted_contract": sorted(
            {
                ref
                for row in (*intents, *preserve)
                if row.get("evidence_class") == "accepted_contract"
                for ref in (
                    row.get("intent_id", ""),
                    row.get("behavior_block_id", ""),
                    *row.get("source_refs", ()),
                    *row.get("evidence_refs", ()),
                )
                if ref
            }
        ),
        "executed_evidence": sorted(
            {
                ref
                for row in validation
                if row.get("evidence_class") == "executed_evidence"
                for ref in (
                    row.get("coverage_id", ""),
                    row.get("execution_evidence_id", ""),
                    row.get("receipt_id", ""),
                )
                if ref
            }
        ),
        "unresolved": sorted(
            {
                ref
                for gap in ordered_gaps
                for ref in (gap.get("gap_id", ""), *gap.get("evidence_refs", ()))
                if ref
            }
        ),
    }
    context: dict[str, Any] = {
        "schema_version": AFFECTED_TASK_CONTEXT_SCHEMA,
        "task_summary": str(task_summary or ""),
        "blueprint_fingerprint": read_result.blueprint_fingerprint,
        "logical_fingerprint": read_result.logical_fingerprint,
        "index_fingerprint": index.fingerprint,
        "status": str(status or _context_scalar(target, "status", default="") or ""),
        "requested_seed_ids": list(read_result.requested_seed_ids),
        "affected_ids": list(read_result.affected_ids),
        "propagated_affected_ids": list(read_result.propagated_affected_ids),
        "selected_change_points": selected,
        "accepted_intent": intents,
        "must_preserve": preserve,
        "impact_paths": impacts,
        "validation": validation,
        "gaps": ordered_gaps,
        "gap_count": len(ordered_gaps),
        "blocker_count": sum(gap.get("status") == "blocked" for gap in ordered_gaps),
        "evidence_boundaries": boundary_refs,
        "accepted_snapshot": snapshot,
        "target_claim_boundary": str(
            _context_scalar(target, "claim_boundary", default="") or ""
        ),
        "claim_boundary": (
            "This task context is a read-only projection of one exact affected "
            "closure. observed_structure, accepted_contract, executed_evidence, "
            "and unresolved are separate; no source call is promoted to semantic "
            "impact and no producer or currentness activation is performed."
        ),
    }
    context["fingerprint"] = fingerprint_value(context)
    return context


@dataclass(frozen=True)
class AffectedBlueprintUnderstanding:
    """AI-facing readiness derived only from one loaded affected closure."""

    scope: str
    blueprint_fingerprint: str
    logical_fingerprint: str
    index_fingerprint: str
    target_system_id: str
    target_profile: str
    subject_revision: str
    descriptor_fingerprint: str
    layer_plan_id: str
    layer_plan_fingerprint: str
    requested_seed_ids: tuple[str, ...]
    affected_ids: tuple[str, ...]
    propagated_affected_ids: tuple[str, ...]
    loaded_shard_ids: tuple[str, ...]
    loaded_object_ids: tuple[str, ...]
    layer_statuses: tuple[tuple[str, str], ...]
    status: str
    deepest_proven_layer: str
    first_gap: BlueprintGapRef | None
    gap_ids: tuple[str, ...]
    gap_count: int
    pre_code_status: str
    executed_evidence_status: str
    implementation_admitted: bool
    native_reports: tuple[BlueprintNativeReportRef, ...]
    required_path_quality_model_ids: tuple[str, ...]
    path_quality_bindings: tuple[ModelPathQualityBlueprintBinding, ...]
    task_context: Mapping[str, Any] = field(default_factory=dict)

    @property
    def schema_version(self) -> str:
        return AFFECTED_BLUEPRINT_UNDERSTANDING_SCHEMA

    @property
    def affected_surface_ids(self) -> tuple[str, ...]:
        return self.affected_ids

    @property
    def fingerprint(self) -> str:
        return fingerprint_value(self.to_dict(include_fingerprint=False))

    @property
    def claim_boundary(self) -> str:
        return (
            "This readiness result is derived from one fingerprint-checked affected "
            "closure and its loaded canonical ledger. It runs no provider, native "
            "validation owner, whole builder, or implementation action."
        )

    def to_dict(self, *, include_fingerprint: bool = True) -> dict[str, Any]:
        payload = {
            "schema_version": self.schema_version,
            "scope": self.scope,
            "blueprint_fingerprint": self.blueprint_fingerprint,
            "logical_fingerprint": self.logical_fingerprint,
            "index_fingerprint": self.index_fingerprint,
            "target_system_id": self.target_system_id,
            "target_profile": self.target_profile,
            "subject_revision": self.subject_revision,
            "descriptor_fingerprint": self.descriptor_fingerprint,
            "layer_plan_id": self.layer_plan_id,
            "layer_plan_fingerprint": self.layer_plan_fingerprint,
            "requested_seed_ids": list(self.requested_seed_ids),
            "affected_ids": list(self.affected_ids),
            "propagated_affected_ids": list(self.propagated_affected_ids),
            "loaded_shard_ids": list(self.loaded_shard_ids),
            "loaded_object_ids": list(self.loaded_object_ids),
            "layer_statuses": [
                {"layer": layer, "status": status}
                for layer, status in self.layer_statuses
            ],
            "status": self.status,
            "deepest_proven_layer": self.deepest_proven_layer,
            "first_gap": (
                {"gap_id": self.first_gap.gap_id, **self.first_gap.to_dict()}
                if self.first_gap
                else None
            ),
            "gap_ids": list(self.gap_ids),
            "gap_count": self.gap_count,
            "pre_code_status": self.pre_code_status,
            "executed_evidence_status": self.executed_evidence_status,
            "implementation_admitted": self.implementation_admitted,
            "native_reports": [row.to_dict() for row in self.native_reports],
            "required_path_quality_model_ids": list(
                self.required_path_quality_model_ids
            ),
            "path_quality_bindings": [
                row.to_dict() for row in self.path_quality_bindings
            ],
            "task_context": _context_safe(self.task_context),
            "claim_boundary": self.claim_boundary,
        }
        if include_fingerprint:
            payload["fingerprint"] = self.fingerprint
        return payload


def _parse_native_report(object_id: str, value: Any) -> BlueprintNativeReportRef:
    payload = _strict_object(
        value,
        required=_NATIVE_REPORT_FIELDS,
        context=f"native report object {object_id}",
    )
    if payload["kind"] != "blueprint_native_report":
        raise AffectedBlueprintReadError(
            f"native report object has the wrong kind: {object_id}"
        )
    try:
        return BlueprintNativeReportRef(
            owner_id=_string(payload["owner_id"], context="native report owner"),
            report_id=_string(payload["report_id"], context="native report id"),
            report_fingerprint=_string(
                payload["report_fingerprint"],
                context="native report fingerprint",
            ),
        )
    except ValueError as exc:
        raise AffectedBlueprintReadError(
            f"native report object is invalid: {object_id}: {exc}"
        ) from exc


def _parse_gap(object_id: str, value: Any) -> BlueprintGapRef:
    payload = _strict_object(
        value,
        required=_GAP_FIELDS,
        context=f"gap object {object_id}",
    )
    if payload["kind"] != "blueprint_gap" or payload["gap_id"] != object_id:
        raise AffectedBlueprintReadError(
            f"gap object identity or kind is invalid: {object_id}"
        )
    try:
        gap = BlueprintGapRef(
            layer=_string(payload["layer"], context="gap layer"),
            object_kind=_string(
                payload["object_kind"], context="gap object kind"
            ),
            object_id=_string(payload["object_id"], context="gap object id"),
            status=_string(payload["status"], context="gap status"),
            owner_id=(
                ""
                if payload["owner_id"] == ""
                else _string(payload["owner_id"], context="gap owner id")
            ),
            evidence_ref=(
                ""
                if payload["evidence_ref"] == ""
                else _string(payload["evidence_ref"], context="gap evidence ref")
            ),
            expected_fingerprint=(
                ""
                if payload["expected_fingerprint"] == ""
                else _string(
                    payload["expected_fingerprint"],
                    context="gap expected fingerprint",
                )
            ),
            observed_fingerprint=(
                ""
                if payload["observed_fingerprint"] == ""
                else _string(
                    payload["observed_fingerprint"],
                    context="gap observed fingerprint",
                )
            ),
            message=_string(payload["message"], context="gap message"),
        )
    except ValueError as exc:
        raise AffectedBlueprintReadError(
            f"gap object is invalid: {object_id}: {exc}"
        ) from exc
    if gap.gap_id != object_id:
        raise AffectedBlueprintReadError(
            f"gap object content does not match its content address: {object_id}"
        )
    return gap


def read_affected_blueprint_understanding(
    index_or_projection: AffectedBlueprintIndex | Mapping[str, Any] | Any,
    *,
    affected_ids: Iterable[str],
    load_shard: ShardLoader,
    load_object: ObjectLoader,
    task_summary: str = "",
    changed_paths: Iterable[str] = (),
    surface_catalog: Mapping[str, Any] | Any | None = None,
    accepted_snapshot: Mapping[str, Any] | Any | None = None,
    accepted_snapshot_verified: bool = False,
    authority_root: str | Path | None = None,
    authority_state: Any | None = None,
) -> AffectedBlueprintUnderstanding:
    """Derive compact readiness without a whole summary or whole conversion."""

    if isinstance(index_or_projection, Mapping):
        index = AffectedBlueprintIndex.from_dict(index_or_projection)
    elif isinstance(index_or_projection, AffectedBlueprintIndex):
        index = index_or_projection
    else:
        try:
            index = AffectedBlueprintIndex(
                blueprint_fingerprint=str(
                    _field(index_or_projection, "blueprint_fingerprint")
                ),
                logical_fingerprint=str(
                    _field(index_or_projection, "logical_fingerprint")
                ),
                target_object_id=str(
                    _field(index_or_projection, "target_object_id")
                ),
                ledger_row_ids=tuple(
                    _ids(_field(index_or_projection, "ledger_row_ids"))
                ),
                object_fingerprints=tuple(
                    _field(index_or_projection, "object_fingerprints")
                ),
                shard_fingerprints=tuple(
                    _field(index_or_projection, "shard_fingerprints")
                ),
                shard_member_ids=tuple(
                    _field(index_or_projection, "shard_member_ids")
                ),
                affected_edges=tuple(
                    _field(index_or_projection, "affected_edges")
                ),
                topology_invalidation_edges=tuple(
                    _field(index_or_projection, "topology_invalidation_edges")
                ),
            )
        except (TypeError, ValueError) as exc:
            raise AffectedBlueprintReadError(
                "normalized projection has no current affected-read ledger index"
            ) from exc

    read_result = read_affected_blueprint(
        index,
        affected_ids=affected_ids,
        load_shard=load_shard,
        load_object=load_object,
    )
    objects = dict(read_result.objects)
    if index.target_object_id not in objects:
        raise AffectedBlueprintReadError(
            "affected closure omitted the target identity object"
        )
    target = _strict_object(
        objects[index.target_object_id],
        required=_TARGET_FIELDS,
        context="affected blueprint target object",
    )
    if target["kind"] != "affected_blueprint_target":
        raise AffectedBlueprintReadError(
            "affected blueprint target object has the wrong kind"
        )
    target_row_ids = _string_array(
        target["ledger_row_ids"], context="target ledger row ids"
    )
    target_refs = _string_array(
        target["referenced_object_ids"], context="target object references"
    )
    if target_row_ids != index.ledger_row_ids or target_refs != index.ledger_row_ids:
        raise AffectedBlueprintReadError(
            "affected blueprint target omits or reorders readiness ledger rows"
        )
    if (
        _string(
            target["blueprint_fingerprint"],
            context="target blueprint fingerprint",
        )
        != index.blueprint_fingerprint
        or _string(
            target["logical_fingerprint"], context="target logical fingerprint"
        )
        != index.logical_fingerprint
    ):
        raise AffectedBlueprintReadError(
            "affected blueprint target identity differs from the normalized index"
        )

    rows: list[BlueprintLayerResult] = []
    gaps_by_id: dict[str, BlueprintGapRef] = {}
    native_by_identity: dict[tuple[str, str], BlueprintNativeReportRef] = {}
    for row_id in index.ledger_row_ids:
        if row_id not in objects:
            raise AffectedBlueprintReadError(
                f"affected closure omitted readiness ledger row: {row_id}"
            )
        payload = _strict_object(
            objects[row_id],
            required=_ROW_FIELDS,
            context=f"readiness ledger row {row_id}",
        )
        if payload["kind"] != "blueprint_readiness_row":
            raise AffectedBlueprintReadError(
                f"readiness ledger row has the wrong kind: {row_id}"
            )
        gap_ids = _string_array(
            payload["gap_ids"], context=f"readiness row {row_id} gap ids"
        )
        native_object_ids = _string_array(
            payload["native_report_object_ids"],
            context=f"readiness row {row_id} native report object ids",
        )
        expected_refs = (*gap_ids, *native_object_ids)
        if _string_array(
            payload["referenced_object_ids"],
            context=f"readiness row {row_id} references",
        ) != expected_refs:
            raise AffectedBlueprintReadError(
                f"readiness ledger row has incomplete references: {row_id}"
            )
        row_gaps: list[BlueprintGapRef] = []
        for gap_id in gap_ids:
            if gap_id not in objects:
                raise AffectedBlueprintReadError(
                    f"affected closure omitted ledger gap: {gap_id}"
                )
            gap = _parse_gap(gap_id, objects[gap_id])
            gaps_by_id[gap_id] = gap
            row_gaps.append(gap)
        native_reports: list[BlueprintNativeReportRef] = []
        for native_object_id in native_object_ids:
            if native_object_id not in objects:
                raise AffectedBlueprintReadError(
                    "affected closure omitted native report object: "
                    + native_object_id
                )
            native = _parse_native_report(
                native_object_id, objects[native_object_id]
            )
            identity = (native.owner_id, native.report_id)
            existing = native_by_identity.get(identity)
            if existing is not None and existing != native:
                raise AffectedBlueprintReadError(
                    "affected closure contains conflicting native report identities"
                )
            if native.report_fingerprint not in _string_array(
                payload["evidence_ids"],
                context=f"readiness row {row_id} evidence ids",
            ):
                raise AffectedBlueprintReadError(
                    f"readiness row does not consume native report evidence: {row_id}"
                )
            native_by_identity[identity] = native
            native_reports.append(native)
        try:
            rows.append(
                BlueprintLayerResult._derived(
                    layer=_string(
                        payload["layer"],
                        context=f"readiness row {row_id} layer",
                    ),
                    status=_string(
                        payload["status"],
                        context=f"readiness row {row_id} status",
                    ),
                    evidence_ids=_string_array(
                        payload["evidence_ids"],
                        context=f"readiness row {row_id} evidence ids",
                    ),
                    gap_ids=gap_ids,
                    native_reports=tuple(native_reports),
                    pre_code_status=_string(
                        payload["pre_code_status"],
                        context=f"readiness row {row_id} pre-code status",
                    ),
                    executed_evidence_status=_string(
                        payload["executed_evidence_status"],
                        context=f"readiness row {row_id} executed-evidence status",
                    ),
                    implementation_admitted=payload[
                        "implementation_admitted"
                    ],
                )
            )
        except (TypeError, ValueError) as exc:
            raise AffectedBlueprintReadError(
                f"readiness ledger row is invalid: {row_id}: {exc}"
            ) from exc

    ordered_gaps = tuple(
        gap
        for row in rows
        for gap_id in row.gap_ids
        for gap in (gaps_by_id[gap_id],)
    )
    if len({gap.gap_id for gap in ordered_gaps}) != len(ordered_gaps):
        raise AffectedBlueprintReadError(
            "affected readiness ledger reuses one gap in multiple rows"
        )
    try:
        ledger = BlueprintReadinessLedger(
            target_profile=_string(
                target["target_profile"], context="affected target profile"
            ),
            rows=tuple(rows),
            gaps=ordered_gaps,
        )
    except ValueError as exc:
        raise AffectedBlueprintReadError(
            f"affected readiness ledger is invalid: {exc}"
        ) from exc
    required_path_quality_model_ids = tuple(
        sorted(
            _string_array(
                target["required_path_quality_model_ids"],
                context="target required path-quality model ids",
            )
        )
    )
    path_quality_bindings: list[ModelPathQualityBlueprintBinding] = []
    for object_id, value in sorted(objects.items()):
        if not isinstance(value, Mapping) or value.get("kind") != "model_path_quality_binding":
            continue
        payload = dict(value)
        payload.pop("kind")
        try:
            path_quality_bindings.append(
                ModelPathQualityBlueprintBinding.from_dict(payload)
            )
        except ValueError as exc:
            raise AffectedBlueprintReadError(
                f"affected path-quality object is invalid: {object_id}: {exc}"
            ) from exc
    loaded_path_model_ids = tuple(
        row.model_element_id for row in path_quality_bindings
    )
    loaded_model_ids: set[str] = set()
    for object_id, value in objects.items():
        if not isinstance(value, Mapping):
            continue
        if value.get("kind") == "model_element":
            loaded_model_ids.add(str(object_id))
        model_element_id = value.get("model_element_id")
        if isinstance(model_element_id, str) and model_element_id:
            loaded_model_ids.add(model_element_id)
    affected_required_model_ids = set(required_path_quality_model_ids).intersection(
        {*read_result.affected_ids, *loaded_model_ids}
    )
    missing_affected_path_ids = tuple(
        sorted(affected_required_model_ids - set(loaded_path_model_ids))
    )
    duplicate_loaded_path_ids = tuple(
        sorted(
            model_id
            for model_id in set(loaded_path_model_ids)
            if loaded_path_model_ids.count(model_id) > 1
        )
    )
    unresolved_loaded_path_ids = tuple(
        sorted(
            row.model_element_id
            for row in path_quality_bindings
            if not row.ready
        )
    )
    if ledger.ok and (
        missing_affected_path_ids
        or duplicate_loaded_path_ids
        or unresolved_loaded_path_ids
    ):
        raise AffectedBlueprintReadError(
            "affected readiness ledger passes despite incomplete path-quality closure: "
            f"missing={list(missing_affected_path_ids)}, "
            f"duplicate={list(duplicate_loaded_path_ids)}, "
            f"unresolved={list(unresolved_loaded_path_ids)}"
        )
    task_context = build_affected_task_context(
        read_result,
        index,
        target=target,
        legacy_gaps=tuple(ledger.gaps),
        status=ledger.status,
        task_summary=task_summary,
        changed_paths=changed_paths,
        surface_catalog=surface_catalog,
        accepted_snapshot=accepted_snapshot,
        accepted_snapshot_verified=accepted_snapshot_verified,
        authority_root=authority_root,
        authority_state=authority_state,
    )
    catalog_mismatches = tuple(
        gap
        for gap in task_context.get("gaps", ())
        if gap.get("code") == "surface_catalog_identity_mismatch"
    )
    if catalog_mismatches:
        raise AffectedBlueprintReadError(
            "surface_catalog_identity_mismatch: "
            + "; ".join(str(gap.get("message", "")) for gap in catalog_mismatches)
        )
    return AffectedBlueprintUnderstanding(
        scope="affected",
        blueprint_fingerprint=index.blueprint_fingerprint,
        logical_fingerprint=index.logical_fingerprint,
        index_fingerprint=index.fingerprint,
        target_system_id=_string(
            target["target_system_id"], context="affected target system id"
        ),
        target_profile=_string(
            target["target_profile"], context="affected target profile"
        ),
        subject_revision=_string(
            target["subject_revision"], context="affected subject revision"
        ),
        descriptor_fingerprint=_string(
            target["descriptor_fingerprint"],
            context="affected descriptor fingerprint",
        ),
        layer_plan_id=_string(
            target["layer_plan_id"], context="affected layer plan id"
        ),
        layer_plan_fingerprint=_string(
            target["layer_plan_fingerprint"],
            context="affected layer plan fingerprint",
        ),
        requested_seed_ids=read_result.requested_seed_ids,
        affected_ids=read_result.affected_ids,
        propagated_affected_ids=read_result.propagated_affected_ids,
        loaded_shard_ids=read_result.shard_ids,
        loaded_object_ids=read_result.object_ids,
        layer_statuses=tuple((row.layer, row.status) for row in ledger.rows),
        status=ledger.status,
        deepest_proven_layer=ledger.deepest_proven_layer,
        first_gap=ledger.first_gap,
        gap_ids=tuple(gap.gap_id for gap in ledger.gaps),
        gap_count=ledger.gap_count,
        pre_code_status=ledger.pre_code_status,
        executed_evidence_status=ledger.executed_evidence_status,
        implementation_admitted=ledger.implementation_admitted,
        native_reports=tuple(native_by_identity.values()),
        required_path_quality_model_ids=required_path_quality_model_ids,
        path_quality_bindings=tuple(
            sorted(
                path_quality_bindings,
                key=lambda row: (
                    row.model_element_id,
                    row.compact_current_fingerprint,
                ),
            )
        ),
        task_context=task_context,
    )


__all__ = [
    "AFFECTED_BLUEPRINT_INDEX_SCHEMA",
    "AFFECTED_BLUEPRINT_READER_SCHEMA",
    "AFFECTED_BLUEPRINT_UNDERSTANDING_SCHEMA",
    "AFFECTED_TASK_CONTEXT_SCHEMA",
    "AFFECTED_IMPACT_PLAN_SCHEMA",
    "AFFECTED_IMPACT_OWNER_DISPOSITIONS",
    "AFFECTED_TOPOLOGY_INVALIDATION_EDGE_SCHEMA",
    "AFFECTED_TOPOLOGY_INVALIDATION_KINDS",
    "AffectedBlueprintIndex",
    "AffectedBlueprintProjection",
    "AffectedBlueprintProjectionBundle",
    "AffectedBlueprintReadError",
    "AffectedBlueprintReadResult",
    "AffectedBlueprintReader",
    "AffectedBlueprintUnderstanding",
    "AffectedImpactOwner",
    "AffectedImpactPlan",
    "AffectedTopologyInvalidationEdge",
    "ObjectLoader",
    "ShardLoader",
    "materialize_affected_blueprint_index",
    "load_affected_blueprint_projection",
    "build_affected_task_context",
    "read_affected_blueprint",
    "read_affected_blueprint_understanding",
]
