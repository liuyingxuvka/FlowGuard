"""Single-file transport and verification for the canonical blueprint projection.

The directory projection in :mod:`flowguard.implementation_blueprint` remains
the only blueprint authority.  This module is deliberately a thin envelope:
it carries that exact manifest and its content-addressed shards so a model can
be exchanged or checked in an isolated directory without loading source code,
providers, or a second model format.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import tempfile
from typing import Any, Mapping

from .evidence_receipts import fingerprint_value
from .implementation_blueprint import (
    BLUEPRINT_SCHEMA_VERSION,
    BlueprintShard,
    BlueprintValidationError,
    CanonicalBlueprintProjection,
    verify_blueprint_projection,
)
from .portable_model import canonical_json_bytes


PORTABLE_BLUEPRINT_BUNDLE_SCHEMA = "flowguard.portable_blueprint_bundle.v1"
PORTABLE_BLUEPRINT_COMPACT_SCHEMA = "flowguard.portable_blueprint_compact.v1"
PORTABLE_STATUS_VALUES = frozenset(
    {
        "ready",
        "complete",
        "incomplete",
        "blocked",
        "stale",
        "unknown",
        "not_run",
        "not_applicable",
        "passed",
        "failed",
        "timeout",
        "skipped",
        "running",
        "error",
    }
)
PORTABLE_BLUEPRINT_CLAIM_BOUNDARY = (
    "A transport envelope over one canonical content-addressed blueprint "
    "projection. It proves projection integrity and preserves readiness "
    "statuses; it does not run providers, source, tests, or implementation work."
)


class PortableBlueprintBundleError(ValueError):
    """Raised when a portable bundle is not exact-current or self-consistent."""


def _text(value: Any, *, context: str, required: bool = True) -> str:
    result = str(value).strip()
    if required and not result:
        raise PortableBlueprintBundleError(f"{context} is required")
    return result


def _status(value: Any, *, context: str) -> str:
    result = _text(value, context=context)
    if result not in PORTABLE_STATUS_VALUES:
        raise PortableBlueprintBundleError(
            f"{context} is not a current status: {result}"
        )
    return result


def _exact_object(value: Any, *, fields: frozenset[str], context: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise PortableBlueprintBundleError(f"{context} must be an object")
    actual = {str(key) for key in value}
    missing = sorted(fields - actual)
    unknown = sorted(actual - fields)
    if missing or unknown:
        raise PortableBlueprintBundleError(
            f"{context} fields are not current: missing={missing}, unknown={unknown}"
        )
    return {str(key): item for key, item in value.items()}


def _reject_duplicate_json_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise PortableBlueprintBundleError(
                f"portable blueprint JSON contains duplicate key: {key}"
            )
        result[key] = value
    return result


def _reject_non_finite_json_constant(value: str) -> Any:
    raise PortableBlueprintBundleError(
        f"portable blueprint JSON contains non-finite number: {value}"
    )


def _projection_from_payload(
    manifest: Mapping[str, Any],
    shard_rows: Any,
) -> CanonicalBlueprintProjection:
    manifest_value = _exact_object(
        manifest,
        fields=frozenset({"schema_version", "blueprint_fingerprint", "shards"}),
        context="portable blueprint manifest",
    )
    if manifest_value["schema_version"] != BLUEPRINT_SCHEMA_VERSION:
        raise PortableBlueprintBundleError("portable blueprint manifest schema is not current")
    if not isinstance(manifest_value["shards"], list):
        raise PortableBlueprintBundleError("portable blueprint manifest shards must be an array")
    if not isinstance(shard_rows, list):
        raise PortableBlueprintBundleError("portable blueprint shard rows must be an array")
    manifest_rows = tuple(manifest_value["shards"])
    if len(manifest_rows) != len(shard_rows):
        raise PortableBlueprintBundleError(
            "portable blueprint manifest and shard counts differ"
        )
    manifest_by_path: dict[str, Mapping[str, Any]] = {}
    for row in manifest_rows:
        if not isinstance(row, Mapping):
            raise PortableBlueprintBundleError("portable blueprint manifest row must be an object")
        path = _text(row.get("relative_path"), context="portable shard path")
        if path in manifest_by_path:
            raise PortableBlueprintBundleError("portable blueprint shard path is duplicated")
        manifest_by_path[path] = row

    shards: list[BlueprintShard] = []
    seen_paths: set[str] = set()
    shard_fields = frozenset(
        {"shard_id", "kind", "relative_path", "member_ids", "payload", "content_fingerprint"}
    )
    for raw in shard_rows:
        row = _exact_object(raw, fields=shard_fields, context="portable blueprint shard")
        path = _text(row["relative_path"], context="portable shard path")
        if path in seen_paths:
            raise PortableBlueprintBundleError("portable blueprint shard path is duplicated")
        seen_paths.add(path)
        manifest_row = manifest_by_path.get(path)
        if manifest_row is None:
            raise PortableBlueprintBundleError(
                "portable blueprint shard is absent from its manifest"
            )
        manifest_projection_row = {
            key: manifest_row.get(key)
            for key in (
                "shard_id",
                "kind",
                "relative_path",
                "member_ids",
                "content_fingerprint",
            )
        }
        if manifest_projection_row != {
            key: row.get(key)
            for key in manifest_projection_row
        }:
            raise PortableBlueprintBundleError(
                "portable blueprint shard differs from its manifest row"
            )
        try:
            shard = BlueprintShard(
                shard_id=str(row["shard_id"]),
                kind=str(row["kind"]),
                relative_path=path,
                member_ids=tuple(str(item) for item in row["member_ids"]),
                payload=tuple(row["payload"]),
                content_fingerprint=str(row["content_fingerprint"]),
            )
        except (BlueprintValidationError, TypeError, ValueError) as exc:
            raise PortableBlueprintBundleError(str(exc)) from exc
        shards.append(shard)
    if set(manifest_by_path) != seen_paths:
        raise PortableBlueprintBundleError(
            "portable blueprint manifest contains a shard absent from its envelope"
        )
    projection = CanonicalBlueprintProjection(
        blueprint_fingerprint=_text(
            manifest_value["blueprint_fingerprint"],
            context="portable blueprint fingerprint",
        ),
        shards=tuple(shards),
    )
    # The projection fingerprint is carried by the envelope, not the canonical
    # directory manifest.  Callers compare it after constructing this object.
    verification = verify_blueprint_projection(
        projection,
        expected_blueprint_fingerprint=projection.blueprint_fingerprint,
    )
    if not verification.ok:
        raise PortableBlueprintBundleError(
            "; ".join(finding.message for finding in verification.findings)
        )
    return projection


@dataclass(frozen=True)
class PortableBlueprintBundle:
    """One exchangeable envelope over the canonical projection."""

    projection: CanonicalBlueprintProjection
    subject_revision: str = ""
    target_profile: str = ""
    static_status: str = "unknown"
    portable_status: str = "ready"
    execution_status: str = "not_run"
    claim_boundary: str = PORTABLE_BLUEPRINT_CLAIM_BOUNDARY

    def __post_init__(self) -> None:
        if not isinstance(self.projection, CanonicalBlueprintProjection):
            raise PortableBlueprintBundleError(
                "portable blueprint bundle requires the canonical projection"
            )
        for name in ("static_status", "portable_status", "execution_status"):
            _status(getattr(self, name), context=name)
        if "reconstruction" in self.claim_boundary.lower():
            raise PortableBlueprintBundleError(
                "portable blueprint claim boundary cannot introduce reconstruction"
            )

    @property
    def blueprint_fingerprint(self) -> str:
        return self.projection.blueprint_fingerprint

    @property
    def projection_fingerprint(self) -> str:
        return self.projection.fingerprint

    @property
    def member_ids(self) -> tuple[str, ...]:
        return tuple(
            sorted(
                {
                    member_id
                    for shard in self.projection.shards
                    for member_id in shard.member_ids
                    if member_id
                }
            )
        )

    def _identity_payload(self) -> dict[str, Any]:
        return {
            "schema_version": PORTABLE_BLUEPRINT_BUNDLE_SCHEMA,
            "blueprint_fingerprint": self.blueprint_fingerprint,
            "projection_fingerprint": self.projection_fingerprint,
            "subject_revision": self.subject_revision,
            "target_profile": self.target_profile,
            "statuses": {
                "static": self.static_status,
                "portable": self.portable_status,
                "execution": self.execution_status,
            },
            "manifest": self.projection.manifest_dict(),
            "shards": [shard.to_dict() for shard in self.projection.shards],
            "claim_boundary": self.claim_boundary,
        }

    @property
    def fingerprint(self) -> str:
        return fingerprint_value(self._identity_payload())

    def to_dict(self) -> dict[str, Any]:
        payload = self._identity_payload()
        payload["bundle_fingerprint"] = fingerprint_value(payload)
        return payload


@dataclass(frozen=True)
class PortableBlueprintVerification:
    ok: bool
    status: str
    bundle_fingerprint: str
    projection_fingerprint: str
    static_status: str
    portable_status: str
    execution_status: str
    member_count: int
    shard_count: int
    findings: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "status": self.status,
            "bundle_fingerprint": self.bundle_fingerprint,
            "projection_fingerprint": self.projection_fingerprint,
            "statuses": {
                "static": self.static_status,
                "portable": self.portable_status,
                "execution": self.execution_status,
            },
            "member_count": self.member_count,
            "shard_count": self.shard_count,
            "findings": list(self.findings),
            "claim_boundary": PORTABLE_BLUEPRINT_CLAIM_BOUNDARY,
        }


def build_portable_blueprint_bundle(
    projection: CanonicalBlueprintProjection,
    *,
    subject_revision: str = "",
    target_profile: str = "",
    static_status: str = "unknown",
    execution_status: str = "not_run",
) -> PortableBlueprintBundle:
    """Wrap one verified canonical projection without copying its authority."""

    verification = verify_blueprint_projection(
        projection,
        expected_blueprint_fingerprint=projection.blueprint_fingerprint,
        expected_projection_fingerprint=projection.fingerprint,
    )
    portable_status = "ready" if verification.ok else "blocked"
    return PortableBlueprintBundle(
        projection=projection,
        subject_revision=str(subject_revision),
        target_profile=str(target_profile),
        static_status=static_status,
        portable_status=portable_status,
        execution_status=execution_status,
    )


def portable_blueprint_from_dict(value: Mapping[str, Any]) -> PortableBlueprintBundle:
    fields = frozenset(
        {
            "schema_version",
            "blueprint_fingerprint",
            "projection_fingerprint",
            "subject_revision",
            "target_profile",
            "statuses",
            "manifest",
            "shards",
            "claim_boundary",
            "bundle_fingerprint",
        }
    )
    payload = _exact_object(value, fields=fields, context="portable blueprint bundle")
    if payload["schema_version"] != PORTABLE_BLUEPRINT_BUNDLE_SCHEMA:
        raise PortableBlueprintBundleError("portable blueprint bundle schema is not current")
    statuses = _exact_object(
        payload["statuses"],
        fields=frozenset({"static", "portable", "execution"}),
        context="portable blueprint statuses",
    )
    static_status = _status(statuses["static"], context="static status")
    portable_status = _status(statuses["portable"], context="portable status")
    execution_status = _status(statuses["execution"], context="execution status")
    projection = _projection_from_payload(payload["manifest"], payload["shards"])
    if str(payload["blueprint_fingerprint"]) != projection.blueprint_fingerprint:
        raise PortableBlueprintBundleError("portable blueprint identity differs from its manifest")
    if str(payload["projection_fingerprint"]) != projection.fingerprint:
        raise PortableBlueprintBundleError("portable blueprint projection fingerprint is stale")
    bundle = PortableBlueprintBundle(
        projection=projection,
        subject_revision=str(payload["subject_revision"]),
        target_profile=str(payload["target_profile"]),
        static_status=static_status,
        portable_status=portable_status,
        execution_status=execution_status,
        claim_boundary=_text(payload["claim_boundary"], context="claim boundary"),
    )
    if str(payload["bundle_fingerprint"]) != bundle.fingerprint:
        raise PortableBlueprintBundleError("portable blueprint bundle fingerprint is stale")
    return bundle


def verify_portable_blueprint_bundle(
    value: PortableBlueprintBundle | Mapping[str, Any],
    *,
    expected_blueprint_fingerprint: str | None = None,
    expected_subject_revision: str | None = None,
) -> PortableBlueprintVerification:
    try:
        bundle = (
            value
            if isinstance(value, PortableBlueprintBundle)
            else portable_blueprint_from_dict(value)
        )
        findings: list[str] = []
        if expected_blueprint_fingerprint is not None and bundle.blueprint_fingerprint != expected_blueprint_fingerprint:
            findings.append("blueprint_fingerprint_mismatch")
        if expected_subject_revision is not None and bundle.subject_revision != expected_subject_revision:
            findings.append("subject_revision_mismatch")
        return PortableBlueprintVerification(
            ok=not findings,
            status="complete" if not findings else "blocked",
            bundle_fingerprint=bundle.fingerprint,
            projection_fingerprint=bundle.projection_fingerprint,
            static_status=bundle.static_status,
            portable_status=bundle.portable_status,
            execution_status=bundle.execution_status,
            member_count=len(bundle.member_ids),
            shard_count=len(bundle.projection.shards),
            findings=tuple(findings),
        )
    except (PortableBlueprintBundleError, TypeError, ValueError) as exc:
        return PortableBlueprintVerification(
            ok=False,
            status="blocked",
            bundle_fingerprint="",
            projection_fingerprint="",
            static_status="unknown",
            portable_status="blocked",
            execution_status="not_run",
            member_count=0,
            shard_count=0,
            findings=(str(exc),),
        )


def serialize_portable_blueprint_bundle(bundle: PortableBlueprintBundle) -> bytes:
    return canonical_json_bytes(bundle.to_dict()) + b"\n"


def write_portable_blueprint_bundle(
    bundle: PortableBlueprintBundle,
    output_path: str | Path,
) -> Path:
    path = Path(output_path)
    if path.exists() and path.is_dir():
        raise PortableBlueprintBundleError("portable blueprint output must be a file")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_name = ""
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary_name = handle.name
            handle.write(serialize_portable_blueprint_bundle(bundle))
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, path)
        temporary_name = ""
    except OSError as exc:
        raise PortableBlueprintBundleError(
            f"cannot atomically write portable blueprint bundle: {exc}"
        ) from exc
    finally:
        if temporary_name:
            try:
                os.unlink(temporary_name)
            except OSError:
                pass
    return path


def load_portable_blueprint_bundle(path: str | Path) -> PortableBlueprintBundle:
    try:
        value = json.loads(
            Path(path).read_text(encoding="utf-8"),
            object_pairs_hook=_reject_duplicate_json_keys,
            parse_constant=_reject_non_finite_json_constant,
        )
    except (OSError, json.JSONDecodeError, PortableBlueprintBundleError) as exc:
        raise PortableBlueprintBundleError(f"cannot load portable blueprint bundle: {exc}") from exc
    return portable_blueprint_from_dict(value)


def compact_portable_blueprint_projection(
    bundle: PortableBlueprintBundle,
    *,
    member_limit: int = 64,
) -> dict[str, Any]:
    if member_limit < 1:
        raise ValueError("member_limit must be positive")
    members = bundle.member_ids
    bounded = list(members[:member_limit])
    payload = {
        "schema_version": PORTABLE_BLUEPRINT_COMPACT_SCHEMA,
        "projection_kind": "portable_blueprint",
        "blueprint_fingerprint": bundle.blueprint_fingerprint,
        "projection_fingerprint": bundle.projection_fingerprint,
        "bundle_fingerprint": bundle.fingerprint,
        "subject_revision": bundle.subject_revision,
        "target_profile": bundle.target_profile,
        "statuses": {
            "static": bundle.static_status,
            "portable": bundle.portable_status,
            "execution": bundle.execution_status,
        },
        "shard_kinds": [shard.kind for shard in bundle.projection.shards],
        "shard_count": len(bundle.projection.shards),
        "member_ids": bounded,
        "omitted_member_count": max(0, len(members) - member_limit),
        "claim_boundary": PORTABLE_BLUEPRINT_CLAIM_BOUNDARY,
    }
    payload["compact_fingerprint"] = fingerprint_value(payload)
    return payload


__all__ = [
    "PORTABLE_BLUEPRINT_BUNDLE_SCHEMA",
    "PORTABLE_BLUEPRINT_CLAIM_BOUNDARY",
    "PORTABLE_BLUEPRINT_COMPACT_SCHEMA",
    "PORTABLE_STATUS_VALUES",
    "PortableBlueprintBundle",
    "PortableBlueprintBundleError",
    "PortableBlueprintVerification",
    "build_portable_blueprint_bundle",
    "compact_portable_blueprint_projection",
    "load_portable_blueprint_bundle",
    "portable_blueprint_from_dict",
    "serialize_portable_blueprint_bundle",
    "verify_portable_blueprint_bundle",
    "write_portable_blueprint_bundle",
]
