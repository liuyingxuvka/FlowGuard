"""Strict native-result to behaviour-blueprint mapping registry.

The native runner owns the rows it actually produced.  This registry is the
small, content-addressed bridge to the larger behaviour blueprint: it names
the exact native rows consumed by each blueprint case and records the current
model/runner input identity.  It is deliberately data-only at runtime; no
Markdown or case-name discovery is performed by the loader.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from .native_case_protocol import (
    NATIVE_CASE_BINDING_SCHEMA,
    NativeCaseBinding,
    NativeCaseProtocolError,
    fingerprint_payload,
)
from .source_identity import source_file_fingerprint


NATIVE_CASE_MAPPING_SCHEMA = "flowguard.native_case_mapping.v1"
DEFAULT_NATIVE_CASE_MAPPING_PATH = (
    Path(".flowguard") / "models" / "native-case-mapping.json"
)


class NativeCaseMappingError(ValueError):
    """The checked-in native case mapping is missing, stale, or malformed."""


def _reject_duplicate_json_keys(
    pairs: list[tuple[str, object]],
) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise NativeCaseMappingError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _sha256(value: Any, *, field_name: str) -> str:
    if not isinstance(value, str) or not value.startswith("sha256:") or len(value) != 71:
        raise NativeCaseMappingError(
            f"{field_name} must be a canonical sha256 fingerprint"
        )
    try:
        int(value[7:], 16)
    except ValueError as exc:
        raise NativeCaseMappingError(
            f"{field_name} must be a canonical sha256 fingerprint"
        ) from exc
    return value


def _text(value: Any, *, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        raise NativeCaseMappingError(f"{field_name} must be normalized text")
    return value


def _text_array(value: Any, *, field_name: str) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise NativeCaseMappingError(f"{field_name} must be an array")
    result: list[str] = []
    for item in value:
        text = _text(item, field_name=field_name)
        if text in result:
            raise NativeCaseMappingError(f"{field_name} contains a duplicate: {text}")
        result.append(text)
    return tuple(result)


def _canonical_mapping_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Return the registry identity with self-referential row fingerprints removed."""

    identity = dict(payload)
    identity.pop("mapping_fingerprint", None)
    raw_bindings = identity.get("bindings")
    if isinstance(raw_bindings, list):
        canonical_bindings: list[Any] = []
        for row in raw_bindings:
            if isinstance(row, Mapping):
                item = dict(row)
                # A row points at the root fingerprint, so including it in the
                # root fingerprint would be circular.  The row's own
                # binding_fingerprint is likewise derived from its content.
                item.pop("mapping_fingerprint", None)
                item.pop("binding_fingerprint", None)
                canonical_bindings.append(item)
            else:
                canonical_bindings.append(row)
        identity["bindings"] = canonical_bindings
    return identity


def _binding_from_payload(value: Any, *, index: int) -> NativeCaseBinding:
    if isinstance(value, NativeCaseBinding):
        return value
    if not isinstance(value, Mapping):
        raise NativeCaseMappingError(f"bindings[{index}] must be an object")
    allowed = {
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
    unknown = sorted(set(value) - allowed)
    if unknown:
        raise NativeCaseMappingError(
            f"bindings[{index}] has unknown fields: {', '.join(unknown)}"
        )
    payload = dict(value)
    schema = payload.pop("schema_version", None)
    if schema not in (None, NATIVE_CASE_BINDING_SCHEMA):
        raise NativeCaseMappingError(f"bindings[{index}] has an unsupported schema")
    declared_fingerprint = payload.pop("binding_fingerprint", None)
    try:
        binding = NativeCaseBinding(**payload)
    except (NativeCaseProtocolError, TypeError, ValueError) as exc:
        raise NativeCaseMappingError(f"bindings[{index}] is invalid: {exc}") from exc
    if declared_fingerprint not in (None, ""):
        if not isinstance(declared_fingerprint, str) or declared_fingerprint != binding.fingerprint:
            raise NativeCaseMappingError(f"bindings[{index}] fingerprint is stale")
    return binding


@dataclass(frozen=True)
class NativeCaseMappingRegistry:
    """One exact, current mapping registry."""

    mapping_fingerprint: str
    source_manifest_fingerprint: str
    source_paths: tuple[str, ...]
    bindings: tuple[NativeCaseBinding, ...]
    # Exact producer rows that are intentionally retained as diagnostic or
    # helper observations rather than blueprint leaf obligations.  These are
    # full qualified native IDs (for example ``case:owner:helper``), not
    # aliases.  A current registry may therefore say "this helper is known
    # and non-authoritative" without weakening the foreign-ID gate for any
    # other row.
    diagnostic_native_case_ids: tuple[str, ...] = ()
    path: str = ""

    def __post_init__(self) -> None:
        mapping_fp = _sha256(self.mapping_fingerprint, field_name="mapping_fingerprint")
        source_fp = _sha256(
            self.source_manifest_fingerprint,
            field_name="source_manifest_fingerprint",
        )
        object.__setattr__(self, "mapping_fingerprint", mapping_fp)
        object.__setattr__(self, "source_manifest_fingerprint", source_fp)
        object.__setattr__(self, "source_paths", _text_array(list(self.source_paths), field_name="source_paths"))
        object.__setattr__(
            self,
            "diagnostic_native_case_ids",
            _text_array(
                list(self.diagnostic_native_case_ids),
                field_name="diagnostic_native_case_ids",
            )
            if self.diagnostic_native_case_ids
            else (),
        )
        rows: list[NativeCaseBinding] = []
        for index, binding in enumerate(self.bindings):
            if not isinstance(binding, NativeCaseBinding):
                raise NativeCaseMappingError(f"bindings[{index}] is not typed")
            if binding.mapping_fingerprint != mapping_fp:
                raise NativeCaseMappingError(
                    f"bindings[{index}] mapping_fingerprint does not match registry"
                )
            rows.append(binding)
        blueprint_ids = [row.blueprint_case_id for row in rows]
        if len(blueprint_ids) != len(set(blueprint_ids)):
            raise NativeCaseMappingError("registry has duplicate blueprint_case_id")
        # One producer row may intentionally satisfy more than one blueprint
        # obligation (for example a repaired benchmark leaf is both the
        # positive witness and the repair-preservation witness).  Reuse is
        # safe only when every projection asks the same observable result
        # contract of that row; incompatible expectations would make one
        # receipt silently certify two different behaviours.
        by_native: dict[tuple[str, str], list[NativeCaseBinding]] = {}
        for row in rows:
            for native_id in row.native_case_ids:
                by_native.setdefault((row.owner_id, native_id), []).append(row)
        for native_key, references in by_native.items():
            if len(references) < 2:
                continue
            signatures = {
                (
                    row.expected_status,
                    row.expected_observed_status or row.expected_status,
                    row.evidence_scope,
                    row.covered_dimensions,
                    row.protected_failure_ids,
                    row.expected_finding_codes,
                )
                for row in references
            }
            if len(signatures) != 1:
                owner, native_id = native_key
                raise NativeCaseMappingError(
                    "incompatible native row reuse: " + owner + ":" + native_id
                )
        object.__setattr__(self, "bindings", tuple(sorted(rows, key=lambda row: row.blueprint_case_id)))
        object.__setattr__(self, "path", str(self.path))

    @property
    def bindings_by_owner(self) -> Mapping[str, tuple[NativeCaseBinding, ...]]:
        grouped: dict[str, list[NativeCaseBinding]] = {}
        for binding in self.bindings:
            grouped.setdefault(binding.owner_id, []).append(binding)
        return {owner: tuple(rows) for owner, rows in sorted(grouped.items())}

    @property
    def blueprint_case_ids(self) -> tuple[str, ...]:
        return tuple(row.blueprint_case_id for row in self.bindings)

    @property
    def native_case_count(self) -> int:
        return sum(len(row.native_case_ids) for row in self.bindings)

    def assert_current_manifest(self, root: str | Path = ".") -> str:
        """Require the mapping to name the exact current model manifest.

        ``source_manifest_fingerprint`` is a source-file identity, not a
        report or a JSON re-serialization.  Checking the canonical source
        bytes here prevents a mapping compiled for an older owner/runner
        inventory from silently becoming the native binding authority.  The
        method is intentionally read-only and never searches for a fallback
        manifest or rewrites the registry.
        """

        root_path = Path(root).expanduser().resolve()
        manifest = root_path / ".flowguard" / "models" / "regression-manifest.json"
        if manifest.is_symlink() or not manifest.is_file():
            raise NativeCaseMappingError(
                "current model regression manifest is missing or a symlink: "
                f"{manifest}"
            )
        try:
            actual = source_file_fingerprint(manifest)
        except (OSError, UnicodeError) as exc:
            raise NativeCaseMappingError(
                f"current model regression manifest is unreadable: {exc}"
            ) from exc
        if actual != self.source_manifest_fingerprint:
            raise NativeCaseMappingError(
                "native case mapping source manifest fingerprint is stale: "
                f"declared={self.source_manifest_fingerprint} actual={actual}"
            )
        return actual

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": NATIVE_CASE_MAPPING_SCHEMA,
            "mapping_fingerprint": self.mapping_fingerprint,
            "source_manifest_fingerprint": self.source_manifest_fingerprint,
            "source_paths": list(self.source_paths),
            "diagnostic_native_case_ids": list(self.diagnostic_native_case_ids),
            "bindings": [row.to_dict() for row in self.bindings],
        }

    @classmethod
    def from_payload(
        cls,
        payload: Mapping[str, Any],
        *,
        path: str = "",
    ) -> "NativeCaseMappingRegistry":
        allowed = {
            "schema_version",
            "mapping_fingerprint",
            "source_manifest_fingerprint",
            "source_paths",
            "diagnostic_native_case_ids",
            "bindings",
        }
        unknown = sorted(set(payload) - allowed)
        if unknown:
            raise NativeCaseMappingError(
                "native case mapping has unknown fields: " + ", ".join(unknown)
            )
        if payload.get("schema_version") != NATIVE_CASE_MAPPING_SCHEMA:
            raise NativeCaseMappingError("native case mapping schema is not current")
        mapping_fp = _sha256(payload.get("mapping_fingerprint"), field_name="mapping_fingerprint")
        source_fp = _sha256(
            payload.get("source_manifest_fingerprint"),
            field_name="source_manifest_fingerprint",
        )
        source_paths = _text_array(payload.get("source_paths"), field_name="source_paths")
        diagnostic_native_case_ids = _text_array(
            payload.get("diagnostic_native_case_ids", []),
            field_name="diagnostic_native_case_ids",
        )
        raw_bindings = payload.get("bindings")
        if not isinstance(raw_bindings, list) or not raw_bindings:
            raise NativeCaseMappingError("native case mapping bindings must be a non-empty array")
        bindings = tuple(
            _binding_from_payload(item, index=index)
            for index, item in enumerate(raw_bindings)
        )
        identity_payload = _canonical_mapping_payload(payload)
        if fingerprint_payload(identity_payload) != mapping_fp:
            raise NativeCaseMappingError("native case mapping fingerprint is stale")
        return cls(
            mapping_fingerprint=mapping_fp,
            source_manifest_fingerprint=source_fp,
            source_paths=source_paths,
            bindings=bindings,
            diagnostic_native_case_ids=diagnostic_native_case_ids,
            path=path,
        )


def compute_native_case_mapping_fingerprint(
    *,
    source_manifest_fingerprint: str,
    source_paths: Sequence[str],
    bindings: Sequence[NativeCaseBinding],
    diagnostic_native_case_ids: Sequence[str] = (),
) -> str:
    """Compute the root fingerprint before assigning it to binding rows.

    The calculation intentionally ignores the self-referential mapping and
    binding fingerprints.  Callers can then rebuild each binding with the
    returned value and serialize a registry whose identity is deterministic.
    """

    source_fp = _sha256(source_manifest_fingerprint, field_name="source_manifest_fingerprint")
    paths = _text_array(list(source_paths), field_name="source_paths")
    diagnostics = _text_array(
        list(diagnostic_native_case_ids),
        field_name="diagnostic_native_case_ids",
    ) if diagnostic_native_case_ids else ()
    payload = {
        "schema_version": NATIVE_CASE_MAPPING_SCHEMA,
        "source_manifest_fingerprint": source_fp,
        "source_paths": list(paths),
        "diagnostic_native_case_ids": list(diagnostics),
        # The registry stores rows in blueprint-case order.  Fingerprinting
        # the same canonical order makes a mapping independent of how a
        # compiler or caller happened to discover its owners.
        "bindings": [
            row.to_dict(include_fingerprint=False)
            for row in sorted(bindings, key=lambda item: item.blueprint_case_id)
        ],
    }
    return fingerprint_payload(_canonical_mapping_payload(payload))


def load_native_case_mapping(
    root_or_path: str | Path = ".",
) -> NativeCaseMappingRegistry:
    """Load exactly one current registry; never discover mappings elsewhere."""

    candidate = Path(root_or_path).expanduser()
    if candidate.is_dir():
        candidate = candidate / DEFAULT_NATIVE_CASE_MAPPING_PATH
    candidate = candidate.resolve()
    original = Path(root_or_path).expanduser()
    if original.is_symlink() or candidate.is_symlink() or not candidate.is_file():
        raise NativeCaseMappingError(f"native case mapping is missing or a symlink: {candidate}")
    try:
        payload = json.loads(
            candidate.read_text(encoding="utf-8"),
            object_pairs_hook=_reject_duplicate_json_keys,
            parse_constant=lambda item: (_ for _ in ()).throw(
                NativeCaseMappingError(f"non-finite JSON number: {item}")
            ),
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise NativeCaseMappingError(f"native case mapping is unreadable: {exc}") from exc
    if not isinstance(payload, Mapping):
        raise NativeCaseMappingError("native case mapping must be an object")
    return NativeCaseMappingRegistry.from_payload(payload, path=str(candidate))


__all__ = [
    "DEFAULT_NATIVE_CASE_MAPPING_PATH",
    "NATIVE_CASE_MAPPING_SCHEMA",
    "NativeCaseMappingError",
    "NativeCaseMappingRegistry",
    "compute_native_case_mapping_fingerprint",
    "load_native_case_mapping",
]
