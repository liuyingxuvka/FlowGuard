"""Independent, content-addressed implementation-surface inventories.

The inventory is deliberately derived from the validation input manifest, not
from FlowGuard models, code contracts, or tests.  It records observed source
facts and explicit terminal dispositions; model bindings remain owned by the
blueprint alignment layer.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path, PurePosixPath
from typing import Any, Callable, Mapping, Sequence

from .portable_model import canonical_identity, canonical_json_bytes
from .source_identity import source_file_fingerprint
from .validation_ownership import resolve_input_manifest


IMPLEMENTATION_INVENTORY_SCHEMA_VERSION = "flowguard.implementation_inventory.v1"

IMPLEMENTATION_DISPOSITION_MODEL = "model_implementation"
IMPLEMENTATION_DISPOSITION_SUPPORTING = "supporting"
IMPLEMENTATION_DISPOSITION_GENERATED = "generated"
IMPLEMENTATION_DISPOSITION_EXTERNAL = "external"
IMPLEMENTATION_DISPOSITION_SCOPED_OUT = "scoped_out"
IMPLEMENTATION_DISPOSITION_DEAD_RETIRE = "dead_retire"
IMPLEMENTATION_DISPOSITION_UNRESOLVED = "unresolved"
IMPLEMENTATION_DISPOSITIONS = (
    IMPLEMENTATION_DISPOSITION_MODEL,
    IMPLEMENTATION_DISPOSITION_SUPPORTING,
    IMPLEMENTATION_DISPOSITION_GENERATED,
    IMPLEMENTATION_DISPOSITION_EXTERNAL,
    IMPLEMENTATION_DISPOSITION_SCOPED_OUT,
    IMPLEMENTATION_DISPOSITION_DEAD_RETIRE,
    IMPLEMENTATION_DISPOSITION_UNRESOLVED,
)
TERMINAL_IMPLEMENTATION_DISPOSITIONS = frozenset(
    set(IMPLEMENTATION_DISPOSITIONS) - {IMPLEMENTATION_DISPOSITION_UNRESOLVED}
)

IMPLEMENTATION_FILE_CATEGORIES = (
    "production",
    "build",
    "config",
    "schema",
    "data",
    "asset",
    "migration",
    "test_oracle",
    "generated",
    "external",
    "excluded",
    "unmatched",
)

IMPLEMENTATION_SURFACE_KINDS = (
    "module",
    "class",
    "function",
    "method",
    "entrypoint",
    "helper",
    "non_code",
)

IMPLEMENTATION_FINDING_SEVERITIES = ("info", "warning", "blocker")


class ImplementationInventoryError(ValueError):
    """Raised when an inventory artifact is not exact current format."""


def _strict_object(
    value: Any,
    *,
    context: str,
    required: Sequence[str],
) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ImplementationInventoryError(f"{context} must be an object")
    if set(value) != set(required):
        difference = sorted(set(value) ^ set(required))
        raise ImplementationInventoryError(
            f"{context} fields differ from the current schema: {difference}"
        )
    return value


def _text(value: Any, *, context: str, allow_empty: bool = False) -> str:
    if not isinstance(value, str) or (not allow_empty and not value.strip()):
        qualifier = "a string" if allow_empty else "a non-empty string"
        raise ImplementationInventoryError(f"{context} must be {qualifier}")
    return value


def _strings(value: Any, *, context: str) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)):
        raise ImplementationInventoryError(f"{context} must be an array")
    result = tuple(_text(item, context=f"{context}[]") for item in value)
    if len(result) != len(set(result)):
        raise ImplementationInventoryError(f"{context} contains duplicate values")
    return result


def _normalized_strings(values: Sequence[str]) -> tuple[str, ...]:
    return tuple(sorted({str(value) for value in values if str(value)}))


def _relative_path(value: Any, *, context: str) -> str:
    text = _text(value, context=context).replace("\\", "/")
    candidate = PurePosixPath(text)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise ImplementationInventoryError(
            f"{context} must remain inside the declared repository boundary"
        )
    return candidate.as_posix()


def _pattern(value: Any, *, context: str) -> str:
    text = _text(value, context=context).replace("\\", "/")
    candidate = PurePosixPath(text)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise ImplementationInventoryError(
            f"{context} must be a repository-relative pattern"
        )
    return text


def implementation_surface_key(path: str, symbol: str) -> str:
    """Return the stable human-readable key used by disposition definitions."""

    return f"{_relative_path(path, context='surface path')}#{symbol or '<module>'}"


def implementation_surface_id(path: str, symbol: str, surface_kind: str) -> str:
    payload = {
        "path": _relative_path(path, context="surface path"),
        "symbol": symbol or "<module>",
        "surface_kind": surface_kind,
    }
    return f"implementation-surface:{canonical_identity(payload).split(':', 1)[1]}"


@dataclass(frozen=True)
class BoundaryExclusion:
    pattern: str
    reason: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "pattern", _pattern(self.pattern, context="exclusion.pattern"))
        _text(self.reason, context="exclusion.reason")

    def to_dict(self) -> dict[str, Any]:
        return {"pattern": self.pattern, "reason": self.reason}

    @classmethod
    def from_dict(cls, value: Any) -> "BoundaryExclusion":
        data = _strict_object(
            value,
            context="boundary exclusion",
            required=("pattern", "reason"),
        )
        return cls(pattern=data["pattern"], reason=data["reason"])


@dataclass(frozen=True)
class SoftwareBoundary:
    boundary_id: str
    subject_revision: str
    production_patterns: tuple[str, ...] = ()
    build_patterns: tuple[str, ...] = ()
    config_patterns: tuple[str, ...] = ()
    schema_patterns: tuple[str, ...] = ()
    data_patterns: tuple[str, ...] = ()
    asset_patterns: tuple[str, ...] = ()
    migration_patterns: tuple[str, ...] = ()
    test_oracle_patterns: tuple[str, ...] = ()
    generated_patterns: tuple[str, ...] = ()
    external_patterns: tuple[str, ...] = ()
    exclusions: tuple[BoundaryExclusion, ...] = ()

    def __post_init__(self) -> None:
        _text(self.boundary_id, context="boundary_id")
        _text(self.subject_revision, context="subject_revision")
        for field_name, patterns in self.pattern_groups().items():
            normalized = tuple(
                _pattern(item, context=f"boundary.{field_name}") for item in patterns
            )
            if len(normalized) != len(set(normalized)):
                raise ImplementationInventoryError(
                    f"boundary.{field_name} contains duplicate patterns"
                )
            object.__setattr__(self, f"{field_name}_patterns", normalized)
        if not isinstance(self.exclusions, tuple):
            object.__setattr__(self, "exclusions", tuple(self.exclusions))
        exclusion_patterns = tuple(item.pattern for item in self.exclusions)
        if len(exclusion_patterns) != len(set(exclusion_patterns)):
            raise ImplementationInventoryError("boundary exclusions contain duplicates")
        if not any(self.pattern_groups().values()) and not self.exclusions:
            raise ImplementationInventoryError("software boundary contains no patterns")

    def pattern_groups(self) -> dict[str, tuple[str, ...]]:
        return {
            "production": self.production_patterns,
            "build": self.build_patterns,
            "config": self.config_patterns,
            "schema": self.schema_patterns,
            "data": self.data_patterns,
            "asset": self.asset_patterns,
            "migration": self.migration_patterns,
            "test_oracle": self.test_oracle_patterns,
            "generated": self.generated_patterns,
            "external": self.external_patterns,
        }

    @property
    def fingerprint(self) -> str:
        return canonical_identity(self.to_dict())

    def to_dict(self) -> dict[str, Any]:
        return {
            "boundary_id": self.boundary_id,
            "subject_revision": self.subject_revision,
            "production_patterns": list(self.production_patterns),
            "build_patterns": list(self.build_patterns),
            "config_patterns": list(self.config_patterns),
            "schema_patterns": list(self.schema_patterns),
            "data_patterns": list(self.data_patterns),
            "asset_patterns": list(self.asset_patterns),
            "migration_patterns": list(self.migration_patterns),
            "test_oracle_patterns": list(self.test_oracle_patterns),
            "generated_patterns": list(self.generated_patterns),
            "external_patterns": list(self.external_patterns),
            "exclusions": [item.to_dict() for item in self.exclusions],
        }

    @classmethod
    def from_dict(cls, value: Any) -> "SoftwareBoundary":
        fields = (
            "boundary_id",
            "subject_revision",
            "production_patterns",
            "build_patterns",
            "config_patterns",
            "schema_patterns",
            "data_patterns",
            "asset_patterns",
            "migration_patterns",
            "test_oracle_patterns",
            "generated_patterns",
            "external_patterns",
            "exclusions",
        )
        data = _strict_object(value, context="software boundary", required=fields)
        if not isinstance(data["exclusions"], list):
            raise ImplementationInventoryError("boundary.exclusions must be an array")
        return cls(
            boundary_id=data["boundary_id"],
            subject_revision=data["subject_revision"],
            production_patterns=_strings(data["production_patterns"], context="production_patterns"),
            build_patterns=_strings(data["build_patterns"], context="build_patterns"),
            config_patterns=_strings(data["config_patterns"], context="config_patterns"),
            schema_patterns=_strings(data["schema_patterns"], context="schema_patterns"),
            data_patterns=_strings(data["data_patterns"], context="data_patterns"),
            asset_patterns=_strings(data["asset_patterns"], context="asset_patterns"),
            migration_patterns=_strings(data["migration_patterns"], context="migration_patterns"),
            test_oracle_patterns=_strings(data["test_oracle_patterns"], context="test_oracle_patterns"),
            generated_patterns=_strings(data["generated_patterns"], context="generated_patterns"),
            external_patterns=_strings(data["external_patterns"], context="external_patterns"),
            exclusions=tuple(BoundaryExclusion.from_dict(item) for item in data["exclusions"]),
        )


@dataclass(frozen=True)
class ImplementationFileDisposition:
    path: str
    category: str
    content_fingerprint: str
    disposition: str
    reason: str
    requires_adapter: bool = False
    adapter_id: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "path", _relative_path(self.path, context="file.path"))
        if self.category not in IMPLEMENTATION_FILE_CATEGORIES:
            raise ImplementationInventoryError(f"unknown file category: {self.category}")
        _text(self.content_fingerprint, context=f"file:{self.path}.content_fingerprint")
        if self.disposition not in IMPLEMENTATION_DISPOSITIONS:
            raise ImplementationInventoryError(f"unknown implementation disposition: {self.disposition}")
        if not isinstance(self.reason, str):
            raise ImplementationInventoryError(f"file:{self.path}.reason must be a string")
        if not isinstance(self.requires_adapter, bool):
            raise ImplementationInventoryError(f"file:{self.path}.requires_adapter must be boolean")
        if not isinstance(self.adapter_id, str):
            raise ImplementationInventoryError(f"file:{self.path}.adapter_id must be a string")
        if self.requires_adapter and not self.adapter_id:
            raise ImplementationInventoryError(
                f"file:{self.path} requires an explicit discovery adapter id"
            )
        if self.disposition in {
            IMPLEMENTATION_DISPOSITION_GENERATED,
            IMPLEMENTATION_DISPOSITION_EXTERNAL,
            IMPLEMENTATION_DISPOSITION_SCOPED_OUT,
            IMPLEMENTATION_DISPOSITION_DEAD_RETIRE,
        } and not self.reason.strip():
            raise ImplementationInventoryError(
                f"file:{self.path} disposition {self.disposition} requires a reason"
            )

    @property
    def terminal(self) -> bool:
        return self.disposition in TERMINAL_IMPLEMENTATION_DISPOSITIONS

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "category": self.category,
            "content_fingerprint": self.content_fingerprint,
            "disposition": self.disposition,
            "reason": self.reason,
            "requires_adapter": self.requires_adapter,
            "adapter_id": self.adapter_id,
        }

    @classmethod
    def from_dict(cls, value: Any) -> "ImplementationFileDisposition":
        fields = (
            "path",
            "category",
            "content_fingerprint",
            "disposition",
            "reason",
            "requires_adapter",
            "adapter_id",
        )
        data = _strict_object(value, context="file disposition", required=fields)
        return cls(**{field: data[field] for field in fields})


@dataclass(frozen=True)
class ImplementationSurface:
    surface_id: str
    path: str
    symbol: str
    surface_kind: str
    parent_surface_id: str
    content_fingerprint: str
    structure_fingerprint: str
    disposition: str
    owning_surface_id: str = ""
    roles: tuple[str, ...] = ()
    parameters: tuple[str, ...] = ()
    calls: tuple[str, ...] = ()
    state_reads: tuple[str, ...] = ()
    state_writes: tuple[str, ...] = ()
    side_effect_candidates: tuple[str, ...] = ()
    dynamic_operations: tuple[str, ...] = ()
    raised_errors: tuple[str, ...] = ()
    returns_value: bool = False
    line_start: int = 0
    line_end: int = 0
    discovery_adapter_id: str = ""

    def __post_init__(self) -> None:
        _text(self.surface_id, context="surface_id")
        object.__setattr__(self, "path", _relative_path(self.path, context="surface.path"))
        _text(self.symbol, context=f"surface:{self.surface_id}.symbol")
        if self.surface_kind not in IMPLEMENTATION_SURFACE_KINDS:
            raise ImplementationInventoryError(f"unknown surface kind: {self.surface_kind}")
        if self.disposition not in IMPLEMENTATION_DISPOSITIONS:
            raise ImplementationInventoryError(f"unknown implementation disposition: {self.disposition}")
        for name in (
            "parent_surface_id",
            "owning_surface_id",
            "discovery_adapter_id",
        ):
            if not isinstance(getattr(self, name), str):
                raise ImplementationInventoryError(f"surface:{self.surface_id}.{name} must be a string")
        _text(self.content_fingerprint, context=f"surface:{self.surface_id}.content_fingerprint")
        _text(self.structure_fingerprint, context=f"surface:{self.surface_id}.structure_fingerprint")
        for name in (
            "roles",
            "parameters",
            "calls",
            "state_reads",
            "state_writes",
            "side_effect_candidates",
            "dynamic_operations",
            "raised_errors",
        ):
            object.__setattr__(self, name, _normalized_strings(getattr(self, name)))
        if not isinstance(self.returns_value, bool):
            raise ImplementationInventoryError(f"surface:{self.surface_id}.returns_value must be boolean")
        if not isinstance(self.line_start, int) or not isinstance(self.line_end, int):
            raise ImplementationInventoryError(f"surface:{self.surface_id} line values must be integers")
        if self.line_start < 0 or self.line_end < self.line_start:
            raise ImplementationInventoryError(f"surface:{self.surface_id} line range is invalid")
    @property
    def behavior_bearing(self) -> bool:
        return bool(
            set(self.roles) & {"entrypoint", "state_writer", "effect_writer", "dynamic"}
            or self.surface_kind == "entrypoint"
        )

    @property
    def terminal(self) -> bool:
        return self.disposition in TERMINAL_IMPLEMENTATION_DISPOSITIONS

    def to_dict(self) -> dict[str, Any]:
        return {
            "surface_id": self.surface_id,
            "path": self.path,
            "symbol": self.symbol,
            "surface_kind": self.surface_kind,
            "parent_surface_id": self.parent_surface_id,
            "content_fingerprint": self.content_fingerprint,
            "structure_fingerprint": self.structure_fingerprint,
            "disposition": self.disposition,
            "owning_surface_id": self.owning_surface_id,
            "roles": list(self.roles),
            "parameters": list(self.parameters),
            "calls": list(self.calls),
            "state_reads": list(self.state_reads),
            "state_writes": list(self.state_writes),
            "side_effect_candidates": list(self.side_effect_candidates),
            "dynamic_operations": list(self.dynamic_operations),
            "raised_errors": list(self.raised_errors),
            "returns_value": self.returns_value,
            "line_start": self.line_start,
            "line_end": self.line_end,
            "discovery_adapter_id": self.discovery_adapter_id,
        }

    @classmethod
    def from_dict(cls, value: Any) -> "ImplementationSurface":
        fields = (
            "surface_id",
            "path",
            "symbol",
            "surface_kind",
            "parent_surface_id",
            "content_fingerprint",
            "structure_fingerprint",
            "disposition",
            "owning_surface_id",
            "roles",
            "parameters",
            "calls",
            "state_reads",
            "state_writes",
            "side_effect_candidates",
            "dynamic_operations",
            "raised_errors",
            "returns_value",
            "line_start",
            "line_end",
            "discovery_adapter_id",
        )
        data = _strict_object(value, context="implementation surface", required=fields)
        tuple_fields = {
            name: _strings(data[name], context=f"surface.{name}")
            for name in (
                "roles",
                "parameters",
                "calls",
                "state_reads",
                "state_writes",
                "side_effect_candidates",
                "dynamic_operations",
                "raised_errors",
            )
        }
        return cls(
            **{
                name: data[name]
                for name in fields
                if name not in tuple_fields
            },
            **tuple_fields,
        )


@dataclass(frozen=True)
class ImplementationInventoryFinding:
    code: str
    message: str
    severity: str = "blocker"
    path: str = ""
    surface_id: str = ""

    def __post_init__(self) -> None:
        _text(self.code, context="finding.code")
        _text(self.message, context=f"finding:{self.code}.message")
        if self.severity not in IMPLEMENTATION_FINDING_SEVERITIES:
            raise ImplementationInventoryError(f"unknown finding severity: {self.severity}")
        if self.path:
            object.__setattr__(self, "path", _relative_path(self.path, context="finding.path"))
        if not isinstance(self.surface_id, str):
            raise ImplementationInventoryError("finding.surface_id must be a string")

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "severity": self.severity,
            "path": self.path,
            "surface_id": self.surface_id,
        }

    @classmethod
    def from_dict(cls, value: Any) -> "ImplementationInventoryFinding":
        fields = ("code", "message", "severity", "path", "surface_id")
        data = _strict_object(value, context="inventory finding", required=fields)
        return cls(**{field: data[field] for field in fields})


@dataclass(frozen=True)
class ImplementationDiscoveryResult:
    adapter_id: str
    path: str
    surfaces: tuple[ImplementationSurface, ...] = ()
    findings: tuple[ImplementationInventoryFinding, ...] = ()

    def __post_init__(self) -> None:
        _text(self.adapter_id, context="discovery.adapter_id")
        object.__setattr__(self, "path", _relative_path(self.path, context="discovery.path"))
        if not isinstance(self.surfaces, tuple):
            object.__setattr__(self, "surfaces", tuple(self.surfaces))
        if not isinstance(self.findings, tuple):
            object.__setattr__(self, "findings", tuple(self.findings))


@dataclass(frozen=True)
class ImplementationSurfaceInventory:
    inventory_id: str
    boundary: SoftwareBoundary
    manifest_fingerprint: str
    file_dispositions: tuple[ImplementationFileDisposition, ...]
    surfaces: tuple[ImplementationSurface, ...]
    findings: tuple[ImplementationInventoryFinding, ...]
    claim_boundary: str

    def __post_init__(self) -> None:
        _text(self.inventory_id, context="inventory_id")
        _text(self.manifest_fingerprint, context="manifest_fingerprint")
        _text(self.claim_boundary, context="inventory.claim_boundary")
        for name in ("file_dispositions", "surfaces", "findings"):
            value = getattr(self, name)
            if not isinstance(value, tuple):
                object.__setattr__(self, name, tuple(value))
        paths = tuple(item.path for item in self.file_dispositions)
        if len(paths) != len(set(paths)):
            raise ImplementationInventoryError("inventory contains duplicate file dispositions")
        surface_ids = tuple(item.surface_id for item in self.surfaces)
        if len(surface_ids) != len(set(surface_ids)):
            raise ImplementationInventoryError("inventory contains duplicate surface ids")
        known = set(surface_ids)
        for surface in self.surfaces:
            if surface.parent_surface_id and surface.parent_surface_id not in known:
                raise ImplementationInventoryError(
                    f"surface {surface.surface_id} has unknown parent {surface.parent_surface_id}"
                )
            if surface.owning_surface_id and surface.owning_surface_id not in known:
                raise ImplementationInventoryError(
                    f"surface {surface.surface_id} has unknown owner {surface.owning_surface_id}"
                )

    @property
    def required_surface_ids(self) -> tuple[str, ...]:
        excluded = {
            IMPLEMENTATION_DISPOSITION_GENERATED,
            IMPLEMENTATION_DISPOSITION_EXTERNAL,
            IMPLEMENTATION_DISPOSITION_SCOPED_OUT,
            IMPLEMENTATION_DISPOSITION_DEAD_RETIRE,
        }
        return tuple(
            sorted(item.surface_id for item in self.surfaces if item.disposition not in excluded)
        )

    @property
    def inventory_fingerprint(self) -> str:
        return canonical_identity(self._identity_payload())

    @property
    def fingerprint(self) -> str:
        return self.inventory_fingerprint

    def _identity_payload(self) -> dict[str, Any]:
        return {
            "schema_version": IMPLEMENTATION_INVENTORY_SCHEMA_VERSION,
            "inventory_id": self.inventory_id,
            "boundary": self.boundary.to_dict(),
            "manifest_fingerprint": self.manifest_fingerprint,
            "file_dispositions": [item.to_dict() for item in self.file_dispositions],
            "surfaces": [item.to_dict() for item in self.surfaces],
            "findings": [item.to_dict() for item in self.findings],
            "claim_boundary": self.claim_boundary,
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            **self._identity_payload(),
            "inventory_fingerprint": self.inventory_fingerprint,
        }

    @classmethod
    def from_dict(cls, value: Any) -> "ImplementationSurfaceInventory":
        fields = (
            "schema_version",
            "inventory_id",
            "boundary",
            "manifest_fingerprint",
            "file_dispositions",
            "surfaces",
            "findings",
            "claim_boundary",
            "inventory_fingerprint",
        )
        data = _strict_object(value, context="implementation inventory", required=fields)
        if data["schema_version"] != IMPLEMENTATION_INVENTORY_SCHEMA_VERSION:
            raise ImplementationInventoryError("implementation inventory schema is not current")
        for name in ("file_dispositions", "surfaces", "findings"):
            if not isinstance(data[name], list):
                raise ImplementationInventoryError(f"inventory.{name} must be an array")
        inventory = cls(
            inventory_id=data["inventory_id"],
            boundary=SoftwareBoundary.from_dict(data["boundary"]),
            manifest_fingerprint=data["manifest_fingerprint"],
            file_dispositions=tuple(
                ImplementationFileDisposition.from_dict(item)
                for item in data["file_dispositions"]
            ),
            surfaces=tuple(ImplementationSurface.from_dict(item) for item in data["surfaces"]),
            findings=tuple(
                ImplementationInventoryFinding.from_dict(item) for item in data["findings"]
            ),
            claim_boundary=data["claim_boundary"],
        )
        expected = _text(data["inventory_fingerprint"], context="inventory_fingerprint")
        if inventory.inventory_fingerprint != expected:
            raise ImplementationInventoryError("implementation inventory fingerprint mismatch")
        return inventory


@dataclass(frozen=True)
class ImplementationInventoryAuditReport:
    ok: bool
    status: str
    inventory_fingerprint: str
    required_surface_ids: tuple[str, ...]
    findings: tuple[ImplementationInventoryFinding, ...]
    claim_boundary: str

    def __post_init__(self) -> None:
        if not isinstance(self.ok, bool):
            raise ImplementationInventoryError("audit report ok must be boolean")
        if self.status not in {"complete", "blocked"}:
            raise ImplementationInventoryError("audit report status must be complete or blocked")
        if not isinstance(self.inventory_fingerprint, str):
            raise ImplementationInventoryError("audit inventory_fingerprint must be a string")
        object.__setattr__(self, "required_surface_ids", _normalized_strings(self.required_surface_ids))
        if not isinstance(self.findings, tuple):
            object.__setattr__(self, "findings", tuple(self.findings))
        _text(self.claim_boundary, context="audit.claim_boundary")

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "status": self.status,
            "inventory_fingerprint": self.inventory_fingerprint,
            "required_surface_ids": list(self.required_surface_ids),
            "findings": [item.to_dict() for item in self.findings],
            "claim_boundary": self.claim_boundary,
        }


DiscoveryAdapter = Callable[..., ImplementationDiscoveryResult]


def _boundary_manifest(
    root: Path,
    boundary: SoftwareBoundary,
) -> tuple[dict[str, str], dict[str, tuple[str, ...]], tuple[ImplementationInventoryFinding, ...]]:
    rows = {
        row["path"]: row["sha256"]
        for row in resolve_input_manifest(root, ("**/*", "*"))
    }
    categories: dict[str, set[str]] = {}
    findings: list[ImplementationInventoryFinding] = []
    groups = {**boundary.pattern_groups(), "excluded": tuple(item.pattern for item in boundary.exclusions)}
    for category, patterns in groups.items():
        if not patterns:
            continue
        for row in resolve_input_manifest(root, patterns):
            path = row["path"]
            categories.setdefault(path, set()).add(category)
    for path in rows:
        if path not in categories:
            categories[path] = {"unmatched"}
            findings.append(
                ImplementationInventoryFinding(
                    "unmatched_boundary_file",
                    "tracked or admitted non-ignored file matches no boundary category",
                    path=path,
                )
            )
    for path, memberships in categories.items():
        # A specific exclusion intentionally narrows a broader admitted pattern.
        # Other overlaps remain ambiguous because they would give one file two
        # incompatible reconstruction roles.
        if "excluded" in memberships:
            categories[path] = {"excluded"}
        elif len(memberships) > 1:
            findings.append(
                ImplementationInventoryFinding(
                    "ambiguous_file_category",
                    f"file matches multiple boundary categories: {', '.join(sorted(memberships))}",
                    path=path,
                )
            )
    return (
        rows,
        {path: tuple(sorted(values)) for path, values in categories.items()},
        tuple(findings),
    )


def build_implementation_surface_inventory(
    root: str | Path,
    boundary: SoftwareBoundary,
    *,
    inventory_id: str,
    file_dispositions: Sequence[ImplementationFileDisposition],
    surface_dispositions: Mapping[str, str] | None = None,
    supporting_owners: Mapping[str, str] | None = None,
    dynamic_allowances: Mapping[str, Sequence[str]] | None = None,
    discovery_adapters: Mapping[str, DiscoveryAdapter] | None = None,
    claim_boundary: str = (
        "Static implementation discovery and disposition only; model bindings, "
        "source-independent reconstruction semantics, and empirical reconstruction are not proven."
    ),
) -> ImplementationSurfaceInventory:
    """Build one independent inventory from the validation-owned file manifest.

    ``surface_dispositions`` and ``supporting_owners`` are keyed by either the
    stable ``path#symbol`` key or the deterministic surface id emitted by an
    adapter.  Missing declarations stay unresolved; they are never inferred as
    complete.
    """

    root_path = Path(root).resolve()
    if not root_path.is_dir():
        raise ImplementationInventoryError(f"inventory root is not a directory: {root_path}")
    _text(inventory_id, context="inventory_id")
    manifest, categories, manifest_findings = _boundary_manifest(root_path, boundary)
    findings = list(manifest_findings)
    disposition_by_path: dict[str, ImplementationFileDisposition] = {}
    for item in file_dispositions:
        if item.path in disposition_by_path:
            findings.append(
                ImplementationInventoryFinding(
                    "duplicate_file_disposition",
                    "file has more than one supplied disposition",
                    path=item.path,
                )
            )
            continue
        disposition_by_path[item.path] = item

    admitted: list[ImplementationFileDisposition] = []
    for path in sorted(manifest):
        memberships = categories.get(path, ())
        category = memberships[0] if len(memberships) == 1 else (memberships[0] if memberships else "excluded")
        supplied = disposition_by_path.get(path)
        if supplied is None:
            findings.append(
                ImplementationInventoryFinding(
                    "missing_file_disposition",
                    "admitted file has no explicit implementation disposition",
                    path=path,
                )
            )
            supplied = ImplementationFileDisposition(
                path=path,
                category=category,
                content_fingerprint=manifest[path],
                disposition=IMPLEMENTATION_DISPOSITION_UNRESOLVED,
                reason="missing explicit file disposition",
            )
        else:
            if supplied.category != category:
                findings.append(
                    ImplementationInventoryFinding(
                        "file_category_mismatch",
                        f"declared {supplied.category}; discovered {category}",
                        path=path,
                    )
                )
            if supplied.content_fingerprint != manifest[path]:
                findings.append(
                    ImplementationInventoryFinding(
                        "stale_file_fingerprint",
                        "declared file fingerprint differs from current content",
                        path=path,
                    )
                )
        admitted.append(supplied)

    for path in sorted(set(disposition_by_path) - set(manifest)):
        findings.append(
            ImplementationInventoryFinding(
                "file_outside_boundary",
                "supplied disposition does not belong to the current boundary manifest",
                path=path,
            )
        )

    adapters = dict(discovery_adapters or {})
    surface_dispositions = dict(surface_dispositions or {})
    supporting_owners = dict(supporting_owners or {})
    dynamic_allowances = dict(dynamic_allowances or {})
    surfaces: list[ImplementationSurface] = []
    seen_surface_ids: set[str] = set()
    for item in admitted:
        if item.disposition == IMPLEMENTATION_DISPOSITION_UNRESOLVED:
            findings.append(
                ImplementationInventoryFinding(
                    "unresolved_file_disposition",
                    "file disposition remains unresolved",
                    path=item.path,
                )
            )
        if not item.requires_adapter:
            continue
        adapter = adapters.get(item.adapter_id)
        if adapter is None:
            findings.append(
                ImplementationInventoryFinding(
                    "missing_discovery_adapter",
                    f"required discovery adapter is unavailable: {item.adapter_id}",
                    path=item.path,
                )
            )
            continue
        try:
            result = adapter(
                root=root_path,
                file_disposition=item,
                surface_dispositions=surface_dispositions,
                supporting_owners=supporting_owners,
                dynamic_allowances=dynamic_allowances,
            )
        except Exception as exc:  # adapters are an untrusted boundary
            findings.append(
                ImplementationInventoryFinding(
                    "discovery_adapter_failure",
                    f"{item.adapter_id} failed: {exc.__class__.__name__}: {exc}",
                    path=item.path,
                )
            )
            continue
        if result.adapter_id != item.adapter_id or result.path != item.path:
            findings.append(
                ImplementationInventoryFinding(
                    "discovery_adapter_identity_mismatch",
                    "adapter result does not bind the requested adapter and file",
                    path=item.path,
                )
            )
        findings.extend(result.findings)
        for surface in result.surfaces:
            if surface.surface_id in seen_surface_ids:
                findings.append(
                    ImplementationInventoryFinding(
                        "duplicate_surface_id",
                        "discovery emitted a duplicate implementation surface id",
                        path=surface.path,
                        surface_id=surface.surface_id,
                    )
                )
                continue
            seen_surface_ids.add(surface.surface_id)
            surfaces.append(surface)

    ordered_files = tuple(sorted(admitted, key=lambda item: item.path))
    ordered_surfaces = tuple(sorted(surfaces, key=lambda item: (item.path, item.line_start, item.symbol)))
    manifest_fingerprint = canonical_identity(
        [{"path": path, "sha256": manifest[path]} for path in sorted(manifest)]
    )
    inventory = ImplementationSurfaceInventory(
        inventory_id=inventory_id,
        boundary=boundary,
        manifest_fingerprint=manifest_fingerprint,
        file_dispositions=ordered_files,
        surfaces=ordered_surfaces,
        findings=tuple(findings),
        claim_boundary=claim_boundary,
    )
    return inventory


def review_implementation_surface_inventory(
    inventory: ImplementationSurfaceInventory,
    *,
    root: str | Path | None = None,
) -> ImplementationInventoryAuditReport:
    """Review inventory completeness and, optionally, current file identity."""

    findings = list(inventory.findings)
    surfaces_by_id = {item.surface_id: item for item in inventory.surfaces}
    for item in inventory.file_dispositions:
        if not item.terminal:
            findings.append(
                ImplementationInventoryFinding(
                    "unresolved_file_disposition",
                    "file disposition is not terminal",
                    path=item.path,
                )
            )
    for surface in inventory.surfaces:
        if not surface.terminal:
            findings.append(
                ImplementationInventoryFinding(
                    "unresolved_surface_disposition",
                    "implementation surface disposition is not terminal",
                    path=surface.path,
                    surface_id=surface.surface_id,
                )
            )
        if surface.behavior_bearing and surface.disposition == IMPLEMENTATION_DISPOSITION_SUPPORTING:
            findings.append(
                ImplementationInventoryFinding(
                    "behavior_surface_marked_supporting",
                    "state/effect/entrypoint behavior cannot be disposed as a pure supporting helper",
                    path=surface.path,
                    surface_id=surface.surface_id,
                )
            )
        if surface.disposition == IMPLEMENTATION_DISPOSITION_SUPPORTING and not surface.owning_surface_id:
            findings.append(
                ImplementationInventoryFinding(
                    "missing_supporting_owner",
                    "supporting surface does not identify one owning model implementation",
                    path=surface.path,
                    surface_id=surface.surface_id,
                )
            )
        if surface.owning_surface_id:
            owner = surfaces_by_id.get(surface.owning_surface_id)
            if owner is None or owner.disposition != IMPLEMENTATION_DISPOSITION_MODEL:
                findings.append(
                    ImplementationInventoryFinding(
                        "invalid_supporting_owner",
                        "supporting surface owner is missing or not a model implementation",
                        path=surface.path,
                        surface_id=surface.surface_id,
                    )
                )
    if root is not None:
        root_path = Path(root).resolve()
        for item in inventory.file_dispositions:
            path = (root_path / item.path).resolve()
            try:
                path.relative_to(root_path)
            except ValueError:
                findings.append(
                    ImplementationInventoryFinding(
                        "path_escape",
                        "inventory path escapes the repository root",
                        path=item.path,
                    )
                )
                continue
            if not path.is_file():
                findings.append(
                    ImplementationInventoryFinding(
                        "missing_current_file",
                        "inventoried file is absent from the current root",
                        path=item.path,
                    )
                )
                continue
            if source_file_fingerprint(path) != item.content_fingerprint:
                findings.append(
                    ImplementationInventoryFinding(
                        "stale_file_fingerprint",
                        "inventoried fingerprint differs from current file content",
                        path=item.path,
                    )
                )

    unique = {
        (item.code, item.message, item.severity, item.path, item.surface_id): item
        for item in findings
    }
    ordered = tuple(
        unique[key]
        for key in sorted(unique, key=lambda item: (item[2], item[0], item[3], item[4], item[1]))
    )
    ok = not any(item.severity == "blocker" for item in ordered)
    return ImplementationInventoryAuditReport(
        ok=ok,
        status="complete" if ok else "blocked",
        inventory_fingerprint=inventory.inventory_fingerprint,
        required_surface_ids=inventory.required_surface_ids,
        findings=ordered,
        claim_boundary=inventory.claim_boundary,
    )


def serialize_implementation_surface_inventory(
    inventory: ImplementationSurfaceInventory,
) -> bytes:
    """Return canonical UTF-8 bytes without writing to the filesystem."""

    return canonical_json_bytes(inventory.to_dict())


def write_implementation_surface_inventory(
    inventory: ImplementationSurfaceInventory,
    path: str | Path,
) -> Path:
    """Explicitly write one canonical inventory artifact."""

    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(serialize_implementation_surface_inventory(inventory) + b"\n")
    return target


def load_implementation_surface_inventory(
    path: str | Path,
) -> ImplementationSurfaceInventory:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ImplementationInventoryError(f"cannot load implementation inventory: {exc}") from exc
    return ImplementationSurfaceInventory.from_dict(value)


def audit_implementation_surface_inventory(
    path: str | Path,
    *,
    root: str | Path | None = None,
) -> ImplementationInventoryAuditReport:
    """Load and audit an inventory without writing or executing missing owners."""

    inventory = load_implementation_surface_inventory(path)
    return review_implementation_surface_inventory(inventory, root=root)


__all__ = [
    "IMPLEMENTATION_INVENTORY_SCHEMA_VERSION",
    "IMPLEMENTATION_DISPOSITION_MODEL",
    "IMPLEMENTATION_DISPOSITION_SUPPORTING",
    "IMPLEMENTATION_DISPOSITION_GENERATED",
    "IMPLEMENTATION_DISPOSITION_EXTERNAL",
    "IMPLEMENTATION_DISPOSITION_SCOPED_OUT",
    "IMPLEMENTATION_DISPOSITION_DEAD_RETIRE",
    "IMPLEMENTATION_DISPOSITION_UNRESOLVED",
    "IMPLEMENTATION_DISPOSITIONS",
    "TERMINAL_IMPLEMENTATION_DISPOSITIONS",
    "IMPLEMENTATION_FILE_CATEGORIES",
    "IMPLEMENTATION_SURFACE_KINDS",
    "ImplementationInventoryError",
    "BoundaryExclusion",
    "SoftwareBoundary",
    "ImplementationFileDisposition",
    "ImplementationSurface",
    "ImplementationInventoryFinding",
    "ImplementationDiscoveryResult",
    "ImplementationSurfaceInventory",
    "ImplementationInventoryAuditReport",
    "implementation_surface_key",
    "implementation_surface_id",
    "build_implementation_surface_inventory",
    "review_implementation_surface_inventory",
    "serialize_implementation_surface_inventory",
    "write_implementation_surface_inventory",
    "load_implementation_surface_inventory",
    "audit_implementation_surface_inventory",
]
