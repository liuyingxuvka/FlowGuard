"""Authoritative project model-system snapshots and atomic revision sets.

This module is a thin join across existing FlowGuard owners.  It identifies
their immutable artifacts and relations; it does not replace ModelMesh,
BehaviorCommitmentLedger, FieldLifecycleMesh, Model-Test Alignment, TestMesh,
PortableSystem, or DevelopmentProcessFlow semantics.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
import hashlib
import json
from pathlib import Path
from pathlib import PurePosixPath, PureWindowsPath
import re
from typing import Any, Iterable, Mapping, Sequence

from .source_identity import source_file_fingerprint


MODEL_INPUT_SCHEMA = "flowguard.model_input_ref.v1"
MODEL_INSTANCE_SCHEMA = "flowguard.model_instance_ref.v1"
AUTHORITY_ENDPOINT_SCHEMA = "flowguard.authority_endpoint_ref.v1"
MODEL_RELATION_SCHEMA = "flowguard.model_relation.v1"
COVERAGE_DIMENSION_SCHEMA = "flowguard.coverage_dimension.v1"
COVERAGE_UNIVERSE_SCHEMA = "flowguard.coverage_universe.v1"
MODEL_SYSTEM_SNAPSHOT_SCHEMA = "flowguard.model_system_snapshot.v1"
MODEL_AUTHORITY_HEAD_SCHEMA = "flowguard.model_authority_head.v1"
MODEL_REVISION_MEMBER_SCHEMA = "flowguard.model_revision_member.v1"
MODEL_REVISION_EVIDENCE_SCHEMA = "flowguard.model_revision_evidence.v1"
MODEL_PREDICTION_REPLAY_REF_SCHEMA = "flowguard.prediction_replay_ref.v1"
MODEL_REVISION_SET_SCHEMA = "flowguard.model_revision_set.v1"
MODEL_ACTIVATION_RECEIPT_SCHEMA = "flowguard.model_activation_receipt.v1"
MODEL_ROLLBACK_EFFECT_SCHEMA = "flowguard.model_rollback_effect.v1"
MODEL_ROLLBACK_CONTRACT_SCHEMA = "flowguard.model_rollback_contract.v1"
MODEL_ROLLBACK_RECEIPT_SCHEMA = "flowguard.model_rollback_receipt.v1"

SUBJECT_OBSERVED_IMPLEMENTATION = "observed_implementation"
SUBJECT_NORMATIVE_TARGET = "normative_target"
SUBJECT_COUNTERFACTUAL_EXPERIMENT = "counterfactual_experiment"
SUBJECT_LANES = frozenset(
    {
        SUBJECT_OBSERVED_IMPLEMENTATION,
        SUBJECT_NORMATIVE_TARGET,
        SUBJECT_COUNTERFACTUAL_EXPERIMENT,
    }
)

LIFECYCLE_CANDIDATE = "candidate"
LIFECYCLE_ACTIVE = "active"
LIFECYCLE_HISTORICAL = "historical"
LIFECYCLE_RETIRED = "retired"
LIFECYCLE_STATES = frozenset(
    {
        LIFECYCLE_CANDIDATE,
        LIFECYCLE_ACTIVE,
        LIFECYCLE_HISTORICAL,
        LIFECYCLE_RETIRED,
    }
)

MODEL_RELATION_KINDS = frozenset(
    {
        "contains",
        "refines",
        "depends_on",
        "delegates_to",
        "consumes",
        "produces_for",
        "realizes",
        "supersedes",
        "validates",
        "shares_kernel_with",
    }
)
AUTHORITY_ENDPOINT_KINDS = frozenset(
    {
        "model_instance",
        "external_surface",
        "behavior_commitment",
        "field_inventory",
        "side_effect_inventory",
        "code_contract",
        "test_evidence",
        "parent_closure",
        "portable_system",
        "development_process",
    }
)

COVERAGE_DIMENSIONS = frozenset(
    {
        "external_surfaces",
        "behavior_commitments",
        "model_instances",
        "fields_state_side_effects",
        "code_contracts",
        "tests_evidence",
    }
)

REVISION_PROPOSED = "proposed"
REVISION_ACCEPTED = "accepted"
REVISION_REJECTED = "rejected"
REVISION_WITHDRAWN = "withdrawn"
REVISION_ROLLED_BACK = "rolled_back"
REVISION_FORWARD_REPAIR = "forward_repair"
REVISION_STATUSES = frozenset(
    {
        REVISION_PROPOSED,
        REVISION_ACCEPTED,
        REVISION_REJECTED,
        REVISION_WITHDRAWN,
        REVISION_ROLLED_BACK,
        REVISION_FORWARD_REPAIR,
    }
)
REVISION_OPERATIONS = frozenset({"add", "replace", "remove"})
REVISION_EVIDENCE_REQUIRED = "required"
REVISION_EVIDENCE_PASS = "pass"
ROLLBACK_EFFECT_DISPOSITIONS = frozenset(
    {"restore", "compensate", "irreversible"}
)
ROLLBACK_RESULT_EXACT = "exact"
ROLLBACK_RESULT_COMPENSATED = "compensated"
ROLLBACK_RESULT_FORWARD_REPAIR = "forward_repair"
ROLLBACK_RESULTS = frozenset(
    {
        ROLLBACK_RESULT_EXACT,
        ROLLBACK_RESULT_COMPENSATED,
        ROLLBACK_RESULT_FORWARD_REPAIR,
    }
)

_SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]*$")


class ModelAuthorityError(ValueError):
    """Raised when model-system authority is ambiguous, stale, or incomplete."""


def canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def canonical_fingerprint(value: Any) -> str:
    return f"sha256:{hashlib.sha256(canonical_json(value).encode('utf-8')).hexdigest()}"


def file_fingerprint(path: str | Path) -> str:
    return source_file_fingerprint(path)


def _text(value: Any, field_name: str, *, minimum: int = 1) -> str:
    result = " ".join(str(value or "").split())
    if len(result) < minimum:
        raise ModelAuthorityError(f"{field_name} must be non-empty and reviewable")
    return result


def _id(value: Any, field_name: str) -> str:
    result = str(value or "").strip()
    if not _ID_RE.fullmatch(result):
        raise ModelAuthorityError(f"{field_name} must be a stable id")
    return result


def _sha(value: Any, field_name: str) -> str:
    result = str(value or "").strip()
    if not _SHA256_RE.fullmatch(result):
        raise ModelAuthorityError(f"{field_name} must be a sha256 fingerprint")
    return result


def _ids(values: Iterable[Any], field_name: str) -> tuple[str, ...]:
    result = tuple(sorted(_id(value, field_name) for value in values))
    if len(result) != len(set(result)):
        raise ModelAuthorityError(f"{field_name} must not contain duplicates")
    return result


def _shas(values: Iterable[Any], field_name: str) -> tuple[str, ...]:
    result = tuple(sorted(_sha(value, field_name) for value in values))
    if len(result) != len(set(result)):
        raise ModelAuthorityError(f"{field_name} must not contain duplicates")
    return result


def _strict(
    value: Any,
    name: str,
    required: Sequence[str],
) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ModelAuthorityError(f"{name} must be an object")
    keys = set(value)
    expected = set(required)
    missing = expected - keys
    unknown = keys - expected
    if missing:
        raise ModelAuthorityError(f"{name} missing fields: {sorted(missing)}")
    if unknown:
        raise ModelAuthorityError(f"{name} has unknown fields: {sorted(unknown)}")
    return value


def _array(value: Any, field_name: str) -> Sequence[Any]:
    if not isinstance(value, list):
        raise ModelAuthorityError(f"{field_name} must be an array")
    return value


def _reject_duplicate_json_keys(
    pairs: Sequence[tuple[str, Any]],
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ModelAuthorityError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


@dataclass(frozen=True)
class ModelInputRef:
    path: str
    sha256: str
    schema: str = MODEL_INPUT_SCHEMA

    def __post_init__(self) -> None:
        raw = str(self.path or "").strip()
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
            raise ModelAuthorityError("model input path must be repository-relative")
        normalized = posix.as_posix()
        object.__setattr__(self, "path", normalized)
        object.__setattr__(self, "sha256", _sha(self.sha256, "model_input.sha256"))
        if self.schema != MODEL_INPUT_SCHEMA:
            raise ModelAuthorityError(f"model input schema must be {MODEL_INPUT_SCHEMA}")

    def to_dict(self) -> dict[str, str]:
        return {"schema": self.schema, "path": self.path, "sha256": self.sha256}

    @classmethod
    def from_dict(cls, value: Any) -> "ModelInputRef":
        data = _strict(value, "model_input", ("schema", "path", "sha256"))
        return cls(
            path=data["path"],
            sha256=data["sha256"],
            schema=data["schema"],
        )


@dataclass(frozen=True)
class ModelInstanceRef:
    logical_model_id: str
    model_kind: str
    model_path: str
    model_sha256: str
    runner_path: str
    runner_sha256: str
    purpose_closure_fingerprint: str
    subject_revision: str
    inputs: tuple[ModelInputRef, ...]
    schema: str = MODEL_INSTANCE_SCHEMA

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "logical_model_id",
            _id(self.logical_model_id, "logical_model_id"),
        )
        object.__setattr__(self, "model_kind", _id(self.model_kind, "model_kind"))
        object.__setattr__(self, "model_path", ModelInputRef(self.model_path, self.model_sha256).path)
        object.__setattr__(self, "model_sha256", _sha(self.model_sha256, "model_sha256"))
        object.__setattr__(self, "runner_path", ModelInputRef(self.runner_path, self.runner_sha256).path)
        object.__setattr__(self, "runner_sha256", _sha(self.runner_sha256, "runner_sha256"))
        object.__setattr__(
            self,
            "purpose_closure_fingerprint",
            _sha(
                self.purpose_closure_fingerprint,
                "purpose_closure_fingerprint",
            ),
        )
        object.__setattr__(
            self,
            "subject_revision",
            _text(self.subject_revision, "subject_revision"),
        )
        inputs = tuple(sorted(self.inputs, key=lambda item: item.path))
        if not inputs:
            raise ModelAuthorityError("model instance requires resolved inputs")
        if any(not isinstance(item, ModelInputRef) for item in inputs):
            raise ModelAuthorityError("model instance inputs must be ModelInputRef")
        paths = tuple(item.path for item in inputs)
        if len(paths) != len(set(paths)):
            raise ModelAuthorityError("model instance input paths must be unique")
        object.__setattr__(self, "inputs", inputs)
        if self.schema != MODEL_INSTANCE_SCHEMA:
            raise ModelAuthorityError(
                f"model instance schema must be {MODEL_INSTANCE_SCHEMA}"
            )

    @property
    def input_inventory_fingerprint(self) -> str:
        return canonical_fingerprint([item.to_dict() for item in self.inputs])

    def identity_payload(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "logical_model_id": self.logical_model_id,
            "model_kind": self.model_kind,
            "model_path": self.model_path,
            "model_sha256": self.model_sha256,
            "runner_path": self.runner_path,
            "runner_sha256": self.runner_sha256,
            "purpose_closure_fingerprint": self.purpose_closure_fingerprint,
            "subject_revision": self.subject_revision,
            "inputs": [item.to_dict() for item in self.inputs],
        }

    @property
    def fingerprint(self) -> str:
        return canonical_fingerprint(self.identity_payload())

    def to_dict(self) -> dict[str, Any]:
        return {
            **self.identity_payload(),
            "input_inventory_fingerprint": self.input_inventory_fingerprint,
            "fingerprint": self.fingerprint,
        }

    @classmethod
    def from_dict(cls, value: Any) -> "ModelInstanceRef":
        data = _strict(
            value,
            "model_instance",
            (
                "schema",
                "logical_model_id",
                "model_kind",
                "model_path",
                "model_sha256",
                "runner_path",
                "runner_sha256",
                "purpose_closure_fingerprint",
                "subject_revision",
                "inputs",
                "input_inventory_fingerprint",
                "fingerprint",
            ),
        )
        result = cls(
            logical_model_id=data["logical_model_id"],
            model_kind=data["model_kind"],
            model_path=data["model_path"],
            model_sha256=data["model_sha256"],
            runner_path=data["runner_path"],
            runner_sha256=data["runner_sha256"],
            purpose_closure_fingerprint=data["purpose_closure_fingerprint"],
            subject_revision=data["subject_revision"],
            inputs=tuple(
                ModelInputRef.from_dict(item)
                for item in _array(data["inputs"], "model_instance.inputs")
            ),
            schema=data["schema"],
        )
        if data["input_inventory_fingerprint"] != result.input_inventory_fingerprint:
            raise ModelAuthorityError("stale model input inventory fingerprint")
        if data["fingerprint"] != result.fingerprint:
            raise ModelAuthorityError("stale model instance fingerprint")
        return result


def build_model_instance_ref(
    root: str | Path,
    *,
    logical_model_id: str,
    model_kind: str,
    model_path: str,
    runner_path: str,
    purpose_closure_fingerprint: str,
    subject_revision: str,
    input_paths: Iterable[str],
) -> ModelInstanceRef:
    """Build one canonical instance from exact repository-relative files."""

    root_path = Path(root).resolve()
    normalized_paths = {
        ModelInputRef(path, "sha256:" + "0" * 64).path
        for path in (*tuple(input_paths), model_path, runner_path)
    }
    inputs: list[ModelInputRef] = []
    for relative in sorted(normalized_paths):
        resolved = (root_path / relative).resolve()
        if root_path not in resolved.parents or not resolved.is_file():
            raise ModelAuthorityError(
                f"model input is missing or escapes repository: {relative}"
            )
        inputs.append(ModelInputRef(relative, file_fingerprint(resolved)))
    by_path = {item.path: item.sha256 for item in inputs}
    normalized_model_path = ModelInputRef(
        model_path,
        "sha256:" + "0" * 64,
    ).path
    normalized_runner_path = ModelInputRef(
        runner_path,
        "sha256:" + "0" * 64,
    ).path
    return ModelInstanceRef(
        logical_model_id=logical_model_id,
        model_kind=model_kind,
        model_path=normalized_model_path,
        model_sha256=by_path[normalized_model_path],
        runner_path=normalized_runner_path,
        runner_sha256=by_path[normalized_runner_path],
        purpose_closure_fingerprint=purpose_closure_fingerprint,
        subject_revision=subject_revision,
        inputs=tuple(inputs),
    )


@dataclass(frozen=True)
class AuthorityEndpointRef:
    endpoint_kind: str
    endpoint_id: str
    fingerprint: str
    owner_route: str
    schema: str = AUTHORITY_ENDPOINT_SCHEMA

    def __post_init__(self) -> None:
        if self.endpoint_kind not in AUTHORITY_ENDPOINT_KINDS:
            raise ModelAuthorityError(
                f"unsupported authority endpoint kind: {self.endpoint_kind}"
            )
        object.__setattr__(
            self,
            "endpoint_id",
            _id(self.endpoint_id, "endpoint_id"),
        )
        object.__setattr__(
            self,
            "fingerprint",
            _sha(self.fingerprint, "endpoint fingerprint"),
        )
        object.__setattr__(
            self,
            "owner_route",
            _id(self.owner_route, "owner_route"),
        )
        if self.schema != AUTHORITY_ENDPOINT_SCHEMA:
            raise ModelAuthorityError(
                f"authority endpoint schema must be {AUTHORITY_ENDPOINT_SCHEMA}"
            )

    def to_dict(self) -> dict[str, str]:
        return {
            "schema": self.schema,
            "endpoint_kind": self.endpoint_kind,
            "endpoint_id": self.endpoint_id,
            "fingerprint": self.fingerprint,
            "owner_route": self.owner_route,
        }

    @classmethod
    def from_dict(cls, value: Any) -> "AuthorityEndpointRef":
        data = _strict(
            value,
            "authority_endpoint",
            (
                "schema",
                "endpoint_kind",
                "endpoint_id",
                "fingerprint",
                "owner_route",
            ),
        )
        return cls(
            endpoint_kind=data["endpoint_kind"],
            endpoint_id=data["endpoint_id"],
            fingerprint=data["fingerprint"],
            owner_route=data["owner_route"],
            schema=data["schema"],
        )


@dataclass(frozen=True)
class ModelRelation:
    relation_id: str
    kind: str
    source: AuthorityEndpointRef
    target: AuthorityEndpointRef
    evidence_fingerprints: tuple[str, ...] = ()
    schema: str = MODEL_RELATION_SCHEMA

    def __post_init__(self) -> None:
        object.__setattr__(self, "relation_id", _id(self.relation_id, "relation_id"))
        if self.kind not in MODEL_RELATION_KINDS:
            raise ModelAuthorityError(f"unsupported model relation kind: {self.kind}")
        if not isinstance(self.source, AuthorityEndpointRef):
            raise ModelAuthorityError("relation source must be AuthorityEndpointRef")
        if not isinstance(self.target, AuthorityEndpointRef):
            raise ModelAuthorityError("relation target must be AuthorityEndpointRef")
        if self.source == self.target:
            raise ModelAuthorityError("model relation cannot reference itself")
        object.__setattr__(
            self,
            "evidence_fingerprints",
            _shas(self.evidence_fingerprints, "evidence_fingerprint"),
        )
        if self.schema != MODEL_RELATION_SCHEMA:
            raise ModelAuthorityError(
                f"model relation schema must be {MODEL_RELATION_SCHEMA}"
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "relation_id": self.relation_id,
            "kind": self.kind,
            "source": self.source.to_dict(),
            "target": self.target.to_dict(),
            "evidence_fingerprints": list(self.evidence_fingerprints),
        }

    @classmethod
    def from_dict(cls, value: Any) -> "ModelRelation":
        data = _strict(
            value,
            "model_relation",
            (
                "schema",
                "relation_id",
                "kind",
                "source",
                "target",
                "evidence_fingerprints",
            ),
        )
        return cls(
            relation_id=data["relation_id"],
            kind=data["kind"],
            source=AuthorityEndpointRef.from_dict(data["source"]),
            target=AuthorityEndpointRef.from_dict(data["target"]),
            evidence_fingerprints=tuple(
                _array(
                    data["evidence_fingerprints"],
                    "model_relation.evidence_fingerprints",
                )
            ),
            schema=data["schema"],
        )


@dataclass(frozen=True)
class CoverageDimension:
    dimension_id: str
    required_ids: tuple[str, ...]
    covered_ids: tuple[str, ...]
    excluded_ids: tuple[str, ...] = ()
    unresolved_ids: tuple[str, ...] = ()
    schema: str = COVERAGE_DIMENSION_SCHEMA

    def __post_init__(self) -> None:
        if self.dimension_id not in COVERAGE_DIMENSIONS:
            raise ModelAuthorityError(
                f"unsupported coverage dimension: {self.dimension_id}"
            )
        for name in (
            "required_ids",
            "covered_ids",
            "excluded_ids",
            "unresolved_ids",
        ):
            object.__setattr__(self, name, _ids(getattr(self, name), name))
        if set(self.excluded_ids) & set(self.required_ids):
            raise ModelAuthorityError(
                "excluded coverage ids cannot remain in required ids"
            )
        if self.schema != COVERAGE_DIMENSION_SCHEMA:
            raise ModelAuthorityError(
                f"coverage dimension schema must be {COVERAGE_DIMENSION_SCHEMA}"
            )

    @property
    def missing_ids(self) -> tuple[str, ...]:
        return tuple(sorted(set(self.required_ids) - set(self.covered_ids)))

    @property
    def extra_ids(self) -> tuple[str, ...]:
        return tuple(sorted(set(self.covered_ids) - set(self.required_ids)))

    @property
    def complete(self) -> bool:
        return (
            not self.missing_ids
            and not self.extra_ids
            and not self.unresolved_ids
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "dimension_id": self.dimension_id,
            "required_ids": list(self.required_ids),
            "covered_ids": list(self.covered_ids),
            "excluded_ids": list(self.excluded_ids),
            "unresolved_ids": list(self.unresolved_ids),
            "missing_ids": list(self.missing_ids),
            "extra_ids": list(self.extra_ids),
            "complete": self.complete,
        }

    @classmethod
    def from_dict(cls, value: Any) -> "CoverageDimension":
        data = _strict(
            value,
            "coverage_dimension",
            (
                "schema",
                "dimension_id",
                "required_ids",
                "covered_ids",
                "excluded_ids",
                "unresolved_ids",
                "missing_ids",
                "extra_ids",
                "complete",
            ),
        )
        result = cls(
            dimension_id=data["dimension_id"],
            required_ids=tuple(_array(data["required_ids"], "required_ids")),
            covered_ids=tuple(_array(data["covered_ids"], "covered_ids")),
            excluded_ids=tuple(_array(data["excluded_ids"], "excluded_ids")),
            unresolved_ids=tuple(
                _array(data["unresolved_ids"], "unresolved_ids")
            ),
            schema=data["schema"],
        )
        if tuple(data["missing_ids"]) != result.missing_ids:
            raise ModelAuthorityError("stale coverage missing_ids")
        if tuple(data["extra_ids"]) != result.extra_ids:
            raise ModelAuthorityError("stale coverage extra_ids")
        if bool(data["complete"]) != result.complete:
            raise ModelAuthorityError("stale coverage complete flag")
        return result


@dataclass(frozen=True)
class CoverageUniverse:
    boundary_id: str
    source_inventory_fingerprint: str
    dimensions: tuple[CoverageDimension, ...]
    claim_boundary: str
    schema: str = COVERAGE_UNIVERSE_SCHEMA

    def __post_init__(self) -> None:
        object.__setattr__(self, "boundary_id", _id(self.boundary_id, "boundary_id"))
        object.__setattr__(
            self,
            "source_inventory_fingerprint",
            _sha(
                self.source_inventory_fingerprint,
                "source_inventory_fingerprint",
            ),
        )
        dimensions = tuple(
            sorted(self.dimensions, key=lambda item: item.dimension_id)
        )
        if any(not isinstance(item, CoverageDimension) for item in dimensions):
            raise ModelAuthorityError(
                "coverage universe dimensions must be CoverageDimension"
            )
        ids = tuple(item.dimension_id for item in dimensions)
        if set(ids) != COVERAGE_DIMENSIONS:
            raise ModelAuthorityError(
                "coverage universe must declare every canonical dimension exactly once"
            )
        object.__setattr__(self, "dimensions", dimensions)
        object.__setattr__(
            self,
            "claim_boundary",
            _text(self.claim_boundary, "coverage claim_boundary", minimum=40),
        )
        if self.schema != COVERAGE_UNIVERSE_SCHEMA:
            raise ModelAuthorityError(
                f"coverage universe schema must be {COVERAGE_UNIVERSE_SCHEMA}"
            )

    @property
    def complete(self) -> bool:
        return all(item.complete for item in self.dimensions)

    @property
    def status(self) -> str:
        return (
            "complete_within_declared_boundary"
            if self.complete
            else "incomplete_within_declared_boundary"
        )

    @property
    def fingerprint(self) -> str:
        return canonical_fingerprint(self.identity_payload())

    def identity_payload(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "boundary_id": self.boundary_id,
            "source_inventory_fingerprint": self.source_inventory_fingerprint,
            "dimensions": [item.to_dict() for item in self.dimensions],
            "claim_boundary": self.claim_boundary,
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            **self.identity_payload(),
            "status": self.status,
            "fingerprint": self.fingerprint,
        }

    @classmethod
    def from_dict(cls, value: Any) -> "CoverageUniverse":
        data = _strict(
            value,
            "coverage_universe",
            (
                "schema",
                "boundary_id",
                "source_inventory_fingerprint",
                "dimensions",
                "claim_boundary",
                "status",
                "fingerprint",
            ),
        )
        result = cls(
            boundary_id=data["boundary_id"],
            source_inventory_fingerprint=data["source_inventory_fingerprint"],
            dimensions=tuple(
                CoverageDimension.from_dict(item)
                for item in _array(data["dimensions"], "dimensions")
            ),
            claim_boundary=data["claim_boundary"],
            schema=data["schema"],
        )
        if data["status"] != result.status:
            raise ModelAuthorityError("stale coverage status")
        if data["fingerprint"] != result.fingerprint:
            raise ModelAuthorityError("stale coverage universe fingerprint")
        return result


@dataclass(frozen=True)
class ModelSystemSnapshot:
    snapshot_id: str
    system_id: str
    subject_lane: str
    lifecycle: str
    subject_revision: str
    root_instance_fingerprints: tuple[str, ...]
    model_instances: tuple[ModelInstanceRef, ...]
    relations: tuple[ModelRelation, ...]
    coverage: CoverageUniverse
    owner_artifact_refs: tuple[AuthorityEndpointRef, ...]
    unresolved_gap_ids: tuple[str, ...]
    claim_boundary: str
    schema: str = MODEL_SYSTEM_SNAPSHOT_SCHEMA

    def __post_init__(self) -> None:
        object.__setattr__(self, "snapshot_id", _id(self.snapshot_id, "snapshot_id"))
        object.__setattr__(self, "system_id", _id(self.system_id, "system_id"))
        if self.subject_lane not in SUBJECT_LANES:
            raise ModelAuthorityError(f"unsupported subject lane: {self.subject_lane}")
        if self.lifecycle not in LIFECYCLE_STATES:
            raise ModelAuthorityError(f"unsupported snapshot lifecycle: {self.lifecycle}")
        object.__setattr__(
            self,
            "subject_revision",
            _text(self.subject_revision, "subject_revision"),
        )
        instances = tuple(
            sorted(self.model_instances, key=lambda item: item.fingerprint)
        )
        if not instances:
            raise ModelAuthorityError("model-system snapshot requires model instances")
        fingerprints = tuple(item.fingerprint for item in instances)
        if len(fingerprints) != len(set(fingerprints)):
            raise ModelAuthorityError(
                "model-system snapshot contains duplicate model instances"
            )
        logical_model_ids = tuple(item.logical_model_id for item in instances)
        if len(logical_model_ids) != len(set(logical_model_ids)):
            raise ModelAuthorityError(
                "one snapshot cannot contain multiple instances of one logical model"
            )
        if any(
            item.subject_revision != self.subject_revision
            for item in instances
        ):
            raise ModelAuthorityError(
                "every model instance must describe the snapshot subject revision"
            )
        object.__setattr__(self, "model_instances", instances)
        roots = _shas(
            self.root_instance_fingerprints,
            "root_instance_fingerprint",
        )
        if not roots or not set(roots) <= set(fingerprints):
            raise ModelAuthorityError(
                "snapshot roots must identify contained model instances"
            )
        object.__setattr__(self, "root_instance_fingerprints", roots)
        relations = tuple(sorted(self.relations, key=lambda item: item.relation_id))
        relation_ids = tuple(item.relation_id for item in relations)
        if len(relation_ids) != len(set(relation_ids)):
            raise ModelAuthorityError("snapshot relation ids must be unique")
        if not isinstance(self.coverage, CoverageUniverse):
            raise ModelAuthorityError("snapshot coverage must be CoverageUniverse")
        owner_refs = tuple(
            sorted(
                self.owner_artifact_refs,
                key=lambda item: (
                    item.endpoint_kind,
                    item.endpoint_id,
                    item.fingerprint,
                ),
            )
        )
        if any(not isinstance(item, AuthorityEndpointRef) for item in owner_refs):
            raise ModelAuthorityError(
                "owner artifacts must be typed AuthorityEndpointRef values"
            )
        owner_keys = tuple(
            (item.endpoint_kind, item.endpoint_id) for item in owner_refs
        )
        if len(owner_keys) != len(set(owner_keys)):
            raise ModelAuthorityError("owner artifact refs must be unique")
        object.__setattr__(self, "owner_artifact_refs", owner_refs)
        owner_fingerprints = {item.fingerprint for item in owner_refs}
        for relation in relations:
            for endpoint in (relation.source, relation.target):
                if endpoint.endpoint_kind == "model_instance":
                    if endpoint.fingerprint not in fingerprints:
                        raise ModelAuthorityError(
                            f"relation {relation.relation_id} references an unknown model instance"
                        )
                elif endpoint.fingerprint not in owner_fingerprints:
                    raise ModelAuthorityError(
                        f"relation {relation.relation_id} references an unbound native owner artifact"
                    )
        object.__setattr__(self, "relations", relations)
        object.__setattr__(
            self,
            "unresolved_gap_ids",
            _ids(self.unresolved_gap_ids, "unresolved_gap_id"),
        )
        object.__setattr__(
            self,
            "claim_boundary",
            _text(self.claim_boundary, "snapshot claim_boundary", minimum=40),
        )
        if self.schema != MODEL_SYSTEM_SNAPSHOT_SCHEMA:
            raise ModelAuthorityError(
                f"snapshot schema must be {MODEL_SYSTEM_SNAPSHOT_SCHEMA}"
            )

    @property
    def fingerprint(self) -> str:
        return canonical_fingerprint(self.identity_payload())

    @property
    def coverage_status(self) -> str:
        if self.unresolved_gap_ids:
            return "incomplete_within_declared_boundary"
        return self.coverage.status

    def identity_payload(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "snapshot_id": self.snapshot_id,
            "system_id": self.system_id,
            "subject_lane": self.subject_lane,
            "lifecycle": self.lifecycle,
            "subject_revision": self.subject_revision,
            "root_instance_fingerprints": list(
                self.root_instance_fingerprints
            ),
            "model_instances": [item.to_dict() for item in self.model_instances],
            "relations": [item.to_dict() for item in self.relations],
            "coverage": self.coverage.to_dict(),
            "owner_artifact_refs": [
                item.to_dict() for item in self.owner_artifact_refs
            ],
            "unresolved_gap_ids": list(self.unresolved_gap_ids),
            "claim_boundary": self.claim_boundary,
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            **self.identity_payload(),
            "coverage_status": self.coverage_status,
            "fingerprint": self.fingerprint,
        }

    @classmethod
    def from_dict(cls, value: Any) -> "ModelSystemSnapshot":
        data = _strict(
            value,
            "model_system_snapshot",
            (
                "schema",
                "snapshot_id",
                "system_id",
                "subject_lane",
                "lifecycle",
                "subject_revision",
                "root_instance_fingerprints",
                "model_instances",
                "relations",
                "coverage",
                "owner_artifact_refs",
                "unresolved_gap_ids",
                "claim_boundary",
                "coverage_status",
                "fingerprint",
            ),
        )
        result = cls(
            snapshot_id=data["snapshot_id"],
            system_id=data["system_id"],
            subject_lane=data["subject_lane"],
            lifecycle=data["lifecycle"],
            subject_revision=data["subject_revision"],
            root_instance_fingerprints=tuple(
                _array(data["root_instance_fingerprints"], "snapshot roots")
            ),
            model_instances=tuple(
                ModelInstanceRef.from_dict(item)
                for item in _array(data["model_instances"], "model_instances")
            ),
            relations=tuple(
                ModelRelation.from_dict(item)
                for item in _array(data["relations"], "relations")
            ),
            coverage=CoverageUniverse.from_dict(data["coverage"]),
            owner_artifact_refs=tuple(
                AuthorityEndpointRef.from_dict(item)
                for item in _array(
                    data["owner_artifact_refs"],
                    "owner_artifact_refs",
                )
            ),
            unresolved_gap_ids=tuple(
                _array(data["unresolved_gap_ids"], "unresolved_gap_ids")
            ),
            claim_boundary=data["claim_boundary"],
            schema=data["schema"],
        )
        if data["coverage_status"] != result.coverage_status:
            raise ModelAuthorityError("stale snapshot coverage status")
        if data["fingerprint"] != result.fingerprint:
            raise ModelAuthorityError("stale model-system snapshot fingerprint")
        return result


@dataclass(frozen=True)
class ModelAuthorityHead:
    system_id: str
    snapshot_fingerprint: str
    subject_revision: str
    generation: int
    accepted_revision_set_fingerprint: str
    previous_snapshot_fingerprint: str
    activation_receipt_fingerprint: str
    schema: str = MODEL_AUTHORITY_HEAD_SCHEMA

    def __post_init__(self) -> None:
        object.__setattr__(self, "system_id", _id(self.system_id, "system_id"))
        for name in (
            "snapshot_fingerprint",
            "accepted_revision_set_fingerprint",
            "activation_receipt_fingerprint",
        ):
            object.__setattr__(self, name, _sha(getattr(self, name), name))
        if self.previous_snapshot_fingerprint:
            object.__setattr__(
                self,
                "previous_snapshot_fingerprint",
                _sha(
                    self.previous_snapshot_fingerprint,
                    "previous_snapshot_fingerprint",
                ),
            )
        object.__setattr__(
            self,
            "subject_revision",
            _text(self.subject_revision, "subject_revision"),
        )
        if (
            not isinstance(self.generation, int)
            or isinstance(self.generation, bool)
            or self.generation < 1
        ):
            raise ModelAuthorityError("authority generation must be a positive integer")
        if self.schema != MODEL_AUTHORITY_HEAD_SCHEMA:
            raise ModelAuthorityError(
                f"authority head schema must be {MODEL_AUTHORITY_HEAD_SCHEMA}"
            )

    @property
    def fingerprint(self) -> str:
        return canonical_fingerprint(self.identity_payload())

    def identity_payload(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "system_id": self.system_id,
            "snapshot_fingerprint": self.snapshot_fingerprint,
            "subject_revision": self.subject_revision,
            "generation": self.generation,
            "accepted_revision_set_fingerprint": (
                self.accepted_revision_set_fingerprint
            ),
            "previous_snapshot_fingerprint": self.previous_snapshot_fingerprint,
            "activation_receipt_fingerprint": (
                self.activation_receipt_fingerprint
            ),
        }

    def to_dict(self) -> dict[str, Any]:
        return {**self.identity_payload(), "fingerprint": self.fingerprint}

    @classmethod
    def from_dict(cls, value: Any) -> "ModelAuthorityHead":
        data = _strict(
            value,
            "model_authority_head",
            (
                "schema",
                "system_id",
                "snapshot_fingerprint",
                "subject_revision",
                "generation",
                "accepted_revision_set_fingerprint",
                "previous_snapshot_fingerprint",
                "activation_receipt_fingerprint",
                "fingerprint",
            ),
        )
        result = cls(
            system_id=data["system_id"],
            snapshot_fingerprint=data["snapshot_fingerprint"],
            subject_revision=data["subject_revision"],
            generation=data["generation"],
            accepted_revision_set_fingerprint=data[
                "accepted_revision_set_fingerprint"
            ],
            previous_snapshot_fingerprint=data[
                "previous_snapshot_fingerprint"
            ],
            activation_receipt_fingerprint=data[
                "activation_receipt_fingerprint"
            ],
            schema=data["schema"],
        )
        if data["fingerprint"] != result.fingerprint:
            raise ModelAuthorityError("stale model authority head fingerprint")
        return result


def write_content_addressed_snapshot(
    root: str | Path,
    snapshot: ModelSystemSnapshot,
) -> Path:
    """Persist one immutable snapshot without changing project authority."""

    root_path = Path(root).resolve()
    digest = snapshot.fingerprint.split(":", 1)[1]
    target = (
        root_path
        / ".flowguard"
        / "model-mesh"
        / "snapshots"
        / f"{digest}.json"
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(
        snapshot.to_dict(),
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    ) + "\n"
    if target.exists():
        if target.read_text(encoding="utf-8") != payload:
            raise ModelAuthorityError(
                "content-addressed snapshot path contains different bytes"
            )
        return target
    temporary = target.with_suffix(".json.tmp")
    temporary.write_text(payload, encoding="utf-8")
    temporary.replace(target)
    return target


def load_model_system_snapshot(path: str | Path) -> ModelSystemSnapshot:
    try:
        payload = json.loads(
            Path(path).read_text(encoding="utf-8"),
            object_pairs_hook=_reject_duplicate_json_keys,
            parse_constant=lambda value: (_ for _ in ()).throw(
                ModelAuthorityError(f"non-finite JSON number: {value}")
            ),
        )
    except (OSError, json.JSONDecodeError, ModelAuthorityError) as exc:
        raise ModelAuthorityError(f"cannot load model-system snapshot: {exc}") from exc
    return ModelSystemSnapshot.from_dict(payload)



from .model_revision_set import (
    ModelActivationReceipt,
    ModelRevisionSet,
    ModelRollbackContract,
    ModelRollbackEffect,
    ModelRollbackReceipt,
    PredictionReplayRef,
    RevisionEvidenceRef,
    RevisionMemberChange,
    derive_affected_closure_fingerprint,
    validate_activation_plan,
    validate_operational_rollback,
    validate_revision_set_snapshots,
)

__all__ = [
    "AUTHORITY_ENDPOINT_KINDS",
    "COVERAGE_DIMENSIONS",
    "LIFECYCLE_ACTIVE",
    "LIFECYCLE_CANDIDATE",
    "LIFECYCLE_HISTORICAL",
    "LIFECYCLE_RETIRED",
    "MODEL_RELATION_KINDS",
    "REVISION_ACCEPTED",
    "REVISION_EVIDENCE_PASS",
    "REVISION_EVIDENCE_REQUIRED",
    "REVISION_FORWARD_REPAIR",
    "REVISION_PROPOSED",
    "REVISION_REJECTED",
    "REVISION_ROLLED_BACK",
    "REVISION_WITHDRAWN",
    "ROLLBACK_RESULT_COMPENSATED",
    "ROLLBACK_RESULT_EXACT",
    "ROLLBACK_RESULT_FORWARD_REPAIR",
    "SUBJECT_COUNTERFACTUAL_EXPERIMENT",
    "SUBJECT_NORMATIVE_TARGET",
    "SUBJECT_OBSERVED_IMPLEMENTATION",
    "AuthorityEndpointRef",
    "CoverageDimension",
    "CoverageUniverse",
    "ModelActivationReceipt",
    "ModelAuthorityError",
    "ModelAuthorityHead",
    "ModelInputRef",
    "ModelInstanceRef",
    "ModelRelation",
    "ModelRevisionSet",
    "ModelRollbackContract",
    "ModelRollbackEffect",
    "ModelRollbackReceipt",
    "ModelSystemSnapshot",
    "PredictionReplayRef",
    "RevisionEvidenceRef",
    "RevisionMemberChange",
    "build_model_instance_ref",
    "canonical_fingerprint",
    "canonical_json",
    "derive_affected_closure_fingerprint",
    "file_fingerprint",
    "load_model_system_snapshot",
    "validate_activation_plan",
    "validate_operational_rollback",
    "validate_revision_set_snapshots",
    "write_content_addressed_snapshot",
]
