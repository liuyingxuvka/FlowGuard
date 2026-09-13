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

from .source_identity import functional_source_fingerprint, source_file_fingerprint


MODEL_INPUT_SCHEMA = "flowguard.model_input_ref.v1"
MODEL_INSTANCE_SCHEMA = "flowguard.model_instance_ref.v2"
AUTHORITY_ENDPOINT_SCHEMA = "flowguard.authority_endpoint_ref.v1"
MODEL_RELATION_SCHEMA = "flowguard.model_relation.v1"
COVERAGE_DIMENSION_SCHEMA = "flowguard.coverage_dimension.v1"
COVERAGE_UNIVERSE_SCHEMA = "flowguard.coverage_universe.v1"
MODEL_SYSTEM_SNAPSHOT_SCHEMA = "flowguard.model_system_snapshot.v2"
MODEL_AUTHORITY_HEAD_SCHEMA = "flowguard.model_authority_head.v2"
MODEL_REVISION_MEMBER_SCHEMA = "flowguard.model_revision_member.v1"
MODEL_REVISION_EVIDENCE_SCHEMA = "flowguard.model_revision_evidence.v1"
MODEL_PREDICTION_REPLAY_REF_SCHEMA = "flowguard.prediction_replay_ref.v1"
MODEL_REVISION_SET_SCHEMA = "flowguard.model_revision_set.v1"
MODEL_ACTIVATION_RECEIPT_SCHEMA = "flowguard.model_activation_receipt.v1"
MODEL_ROLLBACK_EFFECT_SCHEMA = "flowguard.model_rollback_effect.v1"
MODEL_ROLLBACK_CONTRACT_SCHEMA = "flowguard.model_rollback_contract.v1"
MODEL_ROLLBACK_RECEIPT_SCHEMA = "flowguard.model_rollback_receipt.v1"
MODEL_BOUNDARY_CONTRACT_SCHEMA = "flowguard.model_boundary_contract.v2"
MODEL_BOUNDARY_CONTRACT_ARTIFACT_CATEGORY = "boundary-contracts"
# The boundary denominator is owned by the existing model-system authority.
# ContractExhaustion consumes this object, but it is not a native authority
# route and must never acquire a second receipt/owner identity.
BOUNDARY_CONTRACT_OWNER_ROUTE = "authoritative_model_system"
BOUNDARY_CONTRACT_VALIDATOR_SCHEMA = (
    "flowguard.model_boundary_contract_structural_validator.v1"
)

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
        "implements",
        "invokes",
        "affects",
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
        "source_owner",
        "runtime_entry",
        # The coupling denominator is a subordinate, content-addressed
        # artifact of the same current model authority.  It is deliberately
        # an endpoint reference rather than a second pointer/authority.
        "boundary_contract",
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
        "affected_authority_relations",
    }
)
BASE_COVERAGE_DIMENSIONS = frozenset(
    COVERAGE_DIMENSIONS - {"affected_authority_relations"}
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


def boundary_topology_payload(
    model_instances: Iterable[Any],
    relations: Iterable[Any],
) -> dict[str, Any]:
    """Return the pointer-free topology identity used by A05 contracts.

    A boundary contract is a semantic coupling denominator.  Its content
    address must therefore depend only on the finite model/relation graph and
    its evidence identities, never on the snapshot, revision, head, or
    activation that later *binds* that graph into authority.  Runtime relation
    metadata may carry those pointers for diagnostics; they are deliberately
    removed from this identity projection.
    """

    def _relation_payload(value: Any) -> dict[str, Any]:
        if isinstance(value, Mapping):
            payload = dict(value)
        elif hasattr(value, "to_dict"):
            payload = dict(value.to_dict())
        else:
            payload = {
                key: getattr(value, key)
                for key in (
                    "relation_id",
                    "relation_type",
                    "kind",
                    "source_endpoint_kind",
                    "source_endpoint_id",
                    "target_endpoint_kind",
                    "target_endpoint_id",
                    "source_ids",
                    "metadata",
                )
                if hasattr(value, key)
            }
        metadata = payload.get("metadata")
        if isinstance(metadata, Mapping):
            metadata = dict(metadata)
            for key in (
                "authority_snapshot_fingerprint",
                "authority_head_fingerprint",
                "accepted_revision_fingerprint",
            ):
                metadata.pop(key, None)
            payload["metadata"] = metadata
        return payload

    model_payload = []
    for value in model_instances:
        if isinstance(value, Mapping):
            logical_id = value.get("logical_model_id", value.get("model_id", ""))
            fingerprint = value.get("fingerprint", "")
        else:
            logical_id = getattr(value, "logical_model_id", getattr(value, "model_id", ""))
            fingerprint = getattr(value, "fingerprint", "")
        model_payload.append(
            {
                "logical_model_id": str(logical_id),
                "fingerprint": str(fingerprint),
            }
        )
    model_payload.sort(key=lambda item: (item["logical_model_id"], item["fingerprint"]))
    relation_payload = [_relation_payload(value) for value in relations]
    relation_payload.sort(key=lambda item: str(item.get("relation_id", "")))
    return {
        "model_instances": model_payload,
        "relations": relation_payload,
    }


def boundary_topology_fingerprint(
    model_instances: Iterable[Any],
    relations: Iterable[Any],
) -> str:
    """Fingerprint one pointer-free finite topology denominator."""

    return canonical_fingerprint(boundary_topology_payload(model_instances, relations))


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
        """Return the complete functional identity owned by this model."""

        return {
            "schema": self.schema,
            "logical_model_id": self.logical_model_id,
            "model_kind": self.model_kind,
            "model_path": self.model_path,
            "model_sha256": self.model_sha256,
            "runner_path": self.runner_path,
            "runner_sha256": self.runner_sha256,
            "purpose_closure_fingerprint": self.purpose_closure_fingerprint,
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
        inputs.append(
            ModelInputRef(
                relative,
                functional_source_fingerprint(root_path, relative),
            )
        )
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
        if set(ids) not in {BASE_COVERAGE_DIMENSIONS, COVERAGE_DIMENSIONS}:
            raise ModelAuthorityError(
                "coverage universe must declare every base dimension exactly once; affected authority is required when that inventory is present"
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
class AcceptedBoundaryContract:
    """Immutable coupling denominator owned by one model-authority snapshot.

    The contract is intentionally stored as typed JSON payloads instead of
    importing :mod:`flowguard.contract_exhaustion` here.  That keeps the
    authority layer independent of the contract mesh (which already imports
    this module) while retaining the exact axis/group/product identities that
    the mesh must consume.  The artifact is subordinate to the snapshot via
    an ``AuthorityEndpointRef`` of kind ``boundary_contract``; it is never a
    second current pointer.
    """

    contract_id: str
    model_id: str
    boundary_source_id: str
    boundary_source_fingerprint: str
    snapshot_fingerprint: str
    accepted_revision_set_fingerprint: str
    topology_fingerprint: str
    axis_payloads: tuple[Mapping[str, Any], ...]
    interaction_group_payloads: tuple[Mapping[str, Any], ...]
    group_relation_ids: Mapping[str, tuple[str, ...]]
    schema: str = MODEL_BOUNDARY_CONTRACT_SCHEMA

    @staticmethod
    def _json_object(value: Any, field_name: str) -> dict[str, Any]:
        try:
            normalized = json.loads(canonical_json(value))
        except (TypeError, ValueError) as exc:
            raise ModelAuthorityError(
                f"{field_name} must contain canonical JSON values"
            ) from exc
        if not isinstance(normalized, dict):
            raise ModelAuthorityError(f"{field_name} must be an object")
        return normalized

    @classmethod
    def _normalize_axis_payloads(
        cls,
        values: Iterable[Mapping[str, Any]],
    ) -> tuple[Mapping[str, Any], ...]:
        normalized: list[Mapping[str, Any]] = []
        for index, value in enumerate(values):
            payload = cls._json_object(value, f"axis_payloads[{index}]")
            axis_id = _id(payload.get("axis_id"), f"axis_payloads[{index}].axis_id")
            declared = _sha(
                payload.get("axis_fingerprint"),
                f"axis_payloads[{index}].axis_fingerprint",
            )
            identity = dict(payload)
            identity.pop("axis_fingerprint", None)
            if canonical_fingerprint(identity) != declared:
                raise ModelAuthorityError(
                    f"axis payload {axis_id!r} has a stale axis_fingerprint"
                )
            normalized.append(identity | {"axis_fingerprint": declared})
        normalized.sort(key=lambda item: str(item["axis_id"]))
        axis_ids = tuple(str(item["axis_id"]) for item in normalized)
        if not axis_ids or len(axis_ids) != len(set(axis_ids)):
            raise ModelAuthorityError(
                "accepted boundary contract requires unique finite axis payloads"
            )
        return tuple(normalized)

    @classmethod
    def _normalize_group_payloads(
        cls,
        values: Iterable[Mapping[str, Any]],
        *,
        axis_ids: set[str],
    ) -> tuple[Mapping[str, Any], ...]:
        normalized: list[Mapping[str, Any]] = []
        for index, value in enumerate(values):
            payload = cls._json_object(
                value,
                f"interaction_group_payloads[{index}]",
            )
            group_id = _id(
                payload.get("group_id"),
                f"interaction_group_payloads[{index}].group_id",
            )
            declared_axis_ids = payload.get("axis_ids")
            if not isinstance(declared_axis_ids, list):
                raise ModelAuthorityError(
                    f"interaction group {group_id!r} axis_ids must be an array"
                )
            group_axis_ids = tuple(
                _id(item, f"interaction_group_payloads[{index}].axis_id")
                for item in declared_axis_ids
            )
            if len(group_axis_ids) != len(set(group_axis_ids)):
                raise ModelAuthorityError(
                    f"interaction group {group_id!r} axis_ids must be unique"
                )
            if not group_axis_ids or not set(group_axis_ids) <= axis_ids:
                raise ModelAuthorityError(
                    f"interaction group {group_id!r} references an unknown or empty axis"
                )
            signature = payload.get("product_signature")
            if not isinstance(signature, Mapping):
                raise ModelAuthorityError(
                    f"interaction group {group_id!r} requires an accepted product_signature"
                )
            signature_payload = cls._json_object(
                signature,
                f"interaction_group_payloads[{index}].product_signature",
            )
            signature_fingerprint = _sha(
                signature_payload.get("fingerprint"),
                f"interaction_group_payloads[{index}].product_signature.fingerprint",
            )
            signature_identity = dict(signature_payload)
            signature_identity.pop("fingerprint", None)
            if canonical_fingerprint(signature_identity) != signature_fingerprint:
                raise ModelAuthorityError(
                    f"interaction group {group_id!r} has a stale product signature"
                )
            signature_axis_ids = signature_identity.get("axis_ids")
            if not isinstance(signature_axis_ids, list) or set(signature_axis_ids) != set(
                group_axis_ids
            ):
                raise ModelAuthorityError(
                    f"interaction group {group_id!r} product signature axes do not match the group"
                )
            normalized.append(
                dict(payload)
                | {
                    "axis_ids": list(group_axis_ids),
                    "product_signature": signature_identity
                    | {"fingerprint": signature_fingerprint},
                }
            )
        normalized.sort(key=lambda item: str(item["group_id"]))
        group_ids = tuple(str(item["group_id"]) for item in normalized)
        if not group_ids or len(group_ids) != len(set(group_ids)):
            raise ModelAuthorityError(
                "accepted boundary contract requires unique interaction groups"
            )
        return tuple(normalized)

    def __post_init__(self) -> None:
        for name in (
            "contract_id",
            "model_id",
            "boundary_source_id",
        ):
            object.__setattr__(self, name, _id(getattr(self, name), name))
        for name in (
            "boundary_source_fingerprint",
            "snapshot_fingerprint",
            "accepted_revision_set_fingerprint",
            "topology_fingerprint",
        ):
            value = str(getattr(self, name) or "").strip()
            # The snapshot/revision values are authority binding context, not
            # semantic contract content.  They are allowed to be absent on a
            # persisted v2 contract and are supplied by the verified current
            # authority loader when the contract is consumed.
            if name in {"snapshot_fingerprint", "accepted_revision_set_fingerprint"} and not value:
                object.__setattr__(self, name, "")
            else:
                object.__setattr__(self, name, _sha(value, name))
        axes = self._normalize_axis_payloads(self.axis_payloads)
        axis_ids = {str(item["axis_id"]) for item in axes}
        groups = self._normalize_group_payloads(
            self.interaction_group_payloads,
            axis_ids=axis_ids,
        )
        object.__setattr__(self, "axis_payloads", axes)
        object.__setattr__(self, "interaction_group_payloads", groups)
        group_ids = {str(item["group_id"]) for item in groups}
        relation_map = {
            _id(group_id, "group_relation_ids.group_id"): _ids(
                relation_ids,
                f"group_relation_ids[{group_id}]",
            )
            for group_id, relation_ids in dict(self.group_relation_ids).items()
        }
        if set(relation_map) != group_ids or any(
            not relation_ids for relation_ids in relation_map.values()
        ):
            raise ModelAuthorityError(
                "accepted boundary contract relation bindings must cover every group"
            )
        object.__setattr__(
            self,
            "group_relation_ids",
            {key: relation_map[key] for key in sorted(relation_map)},
        )
        if self.schema != MODEL_BOUNDARY_CONTRACT_SCHEMA:
            raise ModelAuthorityError(
                f"boundary contract schema must be {MODEL_BOUNDARY_CONTRACT_SCHEMA}"
            )

    @property
    def fingerprint(self) -> str:
        return canonical_fingerprint(self.identity_payload())

    def identity_payload(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "contract_id": self.contract_id,
            "model_id": self.model_id,
            "boundary_source_id": self.boundary_source_id,
            "boundary_source_fingerprint": self.boundary_source_fingerprint,
            "topology_fingerprint": self.topology_fingerprint,
            "axis_payloads": [dict(item) for item in self.axis_payloads],
            "interaction_group_payloads": [
                dict(item) for item in self.interaction_group_payloads
            ],
            "group_relation_ids": {
                key: list(values)
                for key, values in self.group_relation_ids.items()
            },
        }

    def to_dict(self) -> dict[str, Any]:
        # Do not serialize authority pointers into the content-addressed
        # contract.  The current snapshot/revision/head binding is checked by
        # the authority loader and remains visible in the loaded state, while
        # the contract bytes stay reusable across pointer generations.
        return {**self.identity_payload(), "fingerprint": self.fingerprint}

    @classmethod
    def from_dict(cls, value: Any) -> "AcceptedBoundaryContract":
        data = _strict(
            value,
            "accepted_boundary_contract",
            (
                "schema",
                "contract_id",
                "model_id",
                "boundary_source_id",
                "boundary_source_fingerprint",
                "topology_fingerprint",
                "axis_payloads",
                "interaction_group_payloads",
                "group_relation_ids",
                "fingerprint",
            ),
        )
        relation_map = data["group_relation_ids"]
        if not isinstance(relation_map, Mapping):
            raise ModelAuthorityError(
                "accepted_boundary_contract.group_relation_ids must be an object"
            )
        result = cls(
            contract_id=data["contract_id"],
            model_id=data["model_id"],
            boundary_source_id=data["boundary_source_id"],
            boundary_source_fingerprint=data["boundary_source_fingerprint"],
            snapshot_fingerprint="",
            accepted_revision_set_fingerprint="",
            topology_fingerprint=data["topology_fingerprint"],
            axis_payloads=tuple(
                item for item in _array(data["axis_payloads"], "axis_payloads")
            ),
            interaction_group_payloads=tuple(
                item
                for item in _array(
                    data["interaction_group_payloads"],
                    "interaction_group_payloads",
                )
            ),
            group_relation_ids={
                str(key): tuple(
                    _array(values, f"group_relation_ids[{key}]")
                )
                for key, values in relation_map.items()
            },
            schema=data["schema"],
        )
        if data["fingerprint"] != result.fingerprint:
            raise ModelAuthorityError(
                "stale accepted boundary contract fingerprint"
            )
        return result


def build_boundary_contract(
    *,
    contract_id: str,
    model_id: str,
    boundary_source_id: str,
    boundary_source_fingerprint: str,
    model_instances: Iterable[Any],
    relations: Iterable[Any],
    axis_payloads: Iterable[Mapping[str, Any]],
    interaction_group_payloads: Iterable[Mapping[str, Any]],
    group_relation_ids: Mapping[str, Iterable[str]],
) -> AcceptedBoundaryContract:
    """Build the pointer-free A05 contract from validated semantic inputs.

    The producer intentionally has no snapshot, revision, head, output path,
    or execution receipt input.  Those values are authority binding context
    added by the loader/state transition, so they cannot participate in the
    contract's content address or form a hash cycle.
    """

    return AcceptedBoundaryContract(
        contract_id=contract_id,
        model_id=model_id,
        boundary_source_id=boundary_source_id,
        boundary_source_fingerprint=boundary_source_fingerprint,
        snapshot_fingerprint="",
        accepted_revision_set_fingerprint="",
        topology_fingerprint=boundary_topology_fingerprint(model_instances, relations),
        axis_payloads=tuple(axis_payloads),
        interaction_group_payloads=tuple(interaction_group_payloads),
        group_relation_ids={
            str(group_id): tuple(str(item) for item in relation_ids)
            for group_id, relation_ids in group_relation_ids.items()
        },
    )


def build_boundary_contract_from_snapshot(
    snapshot: "ModelSystemSnapshot",
    *,
    contract_id: str,
    model_id: str,
    axis_payloads: Iterable[Mapping[str, Any]],
    interaction_group_payloads: Iterable[Mapping[str, Any]],
    group_relation_ids: Mapping[str, Iterable[str]],
) -> AcceptedBoundaryContract:
    """Produce one boundary contract from a real finite model snapshot.

    ``build_boundary_contract`` is intentionally a low-level, pointer-free
    constructor.  This adapter is the production boundary: it accepts only a
    complete active observed snapshot, takes the coverage identity and
    topology from that snapshot, and verifies every supplied group relation
    against the snapshot's materialized relations.  It never reads a
    candidate plan, creates an authority endpoint, or changes the current
    pointer.  The resulting contract can therefore be persisted first and
    attached to a later candidate snapshot by the existing revision
    transaction.

    Relation-to-group mapping is required rather than inferred.  A plan's
    relation/materialization fields are candidate data and cannot serve as an
    accepted coupling denominator.
    """

    if not isinstance(snapshot, ModelSystemSnapshot):
        raise ModelAuthorityError(
            "boundary contract producer requires a typed model-system snapshot"
        )
    if (
        snapshot.subject_lane != SUBJECT_OBSERVED_IMPLEMENTATION
        or snapshot.lifecycle != LIFECYCLE_ACTIVE
    ):
        raise ModelAuthorityError(
            "boundary contract producer requires an active observed implementation snapshot"
        )
    if (
        not snapshot.coverage.complete
        or snapshot.coverage_status != "complete_within_declared_boundary"
        or snapshot.unresolved_gap_ids
    ):
        raise ModelAuthorityError(
            "boundary contract producer requires complete accepted coverage without unresolved gaps"
        )

    normalized_model_id = _id(model_id, "model_id")
    snapshot_model_ids = {
        instance.logical_model_id for instance in snapshot.model_instances
    }
    if normalized_model_id not in snapshot_model_ids:
        raise ModelAuthorityError(
            "boundary contract producer model is not materialized in the snapshot"
        )

    relations = tuple(snapshot.relations)
    if not relations:
        raise ModelAuthorityError(
            "boundary contract producer requires materialized topology relations"
        )
    relation_ids = tuple(relation.relation_id for relation in relations)
    if len(relation_ids) != len(set(relation_ids)):
        raise ModelAuthorityError(
            "boundary contract producer requires unique topology relation ids"
        )
    if any(not relation.evidence_fingerprints for relation in relations):
        raise ModelAuthorityError(
            "boundary contract producer requires evidence for every topology relation"
        )

    if not isinstance(group_relation_ids, Mapping):
        raise ModelAuthorityError(
            "boundary contract producer requires an explicit group relation mapping"
        )
    relation_map: dict[str, tuple[str, ...]] = {}
    for group_id, raw_relation_ids in group_relation_ids.items():
        if isinstance(raw_relation_ids, (str, bytes)):
            raise ModelAuthorityError(
                f"boundary contract producer relation mapping is not an array: {group_id!r}"
            )
        try:
            values = tuple(str(item).strip() for item in raw_relation_ids)
        except TypeError as exc:
            raise ModelAuthorityError(
                f"boundary contract producer relation mapping is invalid: {group_id!r}"
            ) from exc
        if not values or any(not value for value in values):
            raise ModelAuthorityError(
                f"boundary contract producer relation mapping is empty: {group_id!r}"
            )
        if len(values) != len(set(values)):
            raise ModelAuthorityError(
                f"boundary contract producer relation mapping repeats ids: {group_id!r}"
            )
        unknown = sorted(set(values) - set(relation_ids))
        if unknown:
            raise ModelAuthorityError(
                "boundary contract producer references unmaterialized relations: "
                + ", ".join(unknown)
            )
        relation_map[str(group_id)] = values
    if not relation_map:
        raise ModelAuthorityError(
            "boundary contract producer requires at least one group relation mapping"
        )

    contract = build_boundary_contract(
        contract_id=contract_id,
        model_id=normalized_model_id,
        boundary_source_id=snapshot.coverage.boundary_id,
        boundary_source_fingerprint=snapshot.coverage.fingerprint,
        model_instances=snapshot.model_instances,
        relations=relations,
        axis_payloads=axis_payloads,
        interaction_group_payloads=interaction_group_payloads,
        group_relation_ids=relation_map,
    )
    for axis in contract.axis_payloads:
        axis_model_id = str(axis.get("model_id") or "").strip()
        values = axis.get("values")
        if axis_model_id != normalized_model_id:
            raise ModelAuthorityError(
                "boundary contract producer axis belongs to a different model"
            )
        if not isinstance(values, list) or not values:
            raise ModelAuthorityError(
                "boundary contract producer requires non-empty finite axis values"
            )
    for group in contract.interaction_group_payloads:
        group_model_id = str(group.get("model_id") or "").strip()
        if group_model_id != normalized_model_id:
            raise ModelAuthorityError(
                "boundary contract producer interaction group belongs to a different model"
            )
        signature = group.get("product_signature")
        if not isinstance(signature, Mapping):
            raise ModelAuthorityError(
                "boundary contract producer requires a product signature for every group"
            )
        if (
            str(signature.get("model_id") or "").strip()
            != normalized_model_id
            or str(signature.get("interaction_group_id") or "").strip()
            != str(group["group_id"])
        ):
            raise ModelAuthorityError(
                "boundary contract producer product signature identity is foreign"
            )
    contract_group_ids = {
        str(item["group_id"]) for item in contract.interaction_group_payloads
    }
    if set(relation_map) != contract_group_ids:
        raise ModelAuthorityError(
            "boundary contract producer relation mapping does not cover every interaction group"
        )
    # Re-run the same structural proof used by candidate construction and the
    # authority loader.  This makes the producer's result independently
    # content-addressed before any endpoint or revision binding exists.
    validate_accepted_boundary_contract_for_snapshot(
        contract,
        snapshot,
        require_endpoint=False,
    )
    return contract


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


def validate_accepted_boundary_contract_for_snapshot(
    contract: AcceptedBoundaryContract,
    snapshot: ModelSystemSnapshot,
    *,
    require_endpoint: bool = True,
) -> str:
    """Recompute the structural boundary contract proof for one snapshot.

    This is deliberately shared by the producer, candidate inventory, and
    authority loader.  The contract's obligation ids are not sufficient
    evidence: every consumer must re-check the same finite source, topology,
    axes, groups, relation map, and native owner binding.  The returned
    fingerprint is a content-addressed validator result that callers should
    bind into their owner contract/evidence inputs.

    ``require_endpoint=False`` is used only while producing a new contract
    from an already accepted snapshot, before the endpoint can be attached.
    If a source snapshot already has a boundary endpoint, it must still be
    the exact contract under validation; a foreign endpoint is never ignored.
    """

    if not isinstance(contract, AcceptedBoundaryContract):
        raise ModelAuthorityError(
            "boundary structural validation requires a typed accepted contract"
        )
    if not isinstance(snapshot, ModelSystemSnapshot):
        raise ModelAuthorityError(
            "boundary structural validation requires a typed model snapshot"
        )
    if (
        snapshot.subject_lane != SUBJECT_OBSERVED_IMPLEMENTATION
        or snapshot.lifecycle != LIFECYCLE_ACTIVE
    ):
        raise ModelAuthorityError(
            "boundary structural validation requires an active observed snapshot"
        )
    if (
        not snapshot.coverage.complete
        or snapshot.coverage_status != "complete_within_declared_boundary"
        or snapshot.unresolved_gap_ids
    ):
        raise ModelAuthorityError(
            "boundary structural validation requires complete accepted coverage"
        )

    model_ids = {
        instance.logical_model_id for instance in snapshot.model_instances
    }
    if contract.model_id not in model_ids:
        raise ModelAuthorityError(
            "accepted boundary contract model is not materialized in the snapshot"
        )
    if (
        contract.boundary_source_id != snapshot.coverage.boundary_id
        or contract.boundary_source_fingerprint != snapshot.coverage.fingerprint
    ):
        raise ModelAuthorityError(
            "accepted boundary contract source is stale or foreign"
        )
    topology_fingerprint = boundary_topology_fingerprint(
        snapshot.model_instances,
        snapshot.relations,
    )
    if contract.topology_fingerprint != topology_fingerprint:
        raise ModelAuthorityError(
            "accepted boundary contract topology fingerprint is stale"
        )

    relation_by_id = {relation.relation_id: relation for relation in snapshot.relations}
    if len(relation_by_id) != len(snapshot.relations):
        raise ModelAuthorityError(
            "boundary structural validation requires unique topology relations"
        )
    if any(not relation.evidence_fingerprints for relation in snapshot.relations):
        raise ModelAuthorityError(
            "boundary structural validation requires evidence for every topology relation"
        )

    for axis in contract.axis_payloads:
        if str(axis.get("model_id") or "").strip() != contract.model_id:
            raise ModelAuthorityError(
                "accepted boundary contract axis is owned by a foreign model"
            )
        values = axis.get("values")
        if not isinstance(values, list) or not values:
            raise ModelAuthorityError(
                "accepted boundary contract axis must have finite values"
            )
    group_ids = {
        str(group.get("group_id") or "").strip()
        for group in contract.interaction_group_payloads
    }
    for group in contract.interaction_group_payloads:
        if str(group.get("model_id") or "").strip() != contract.model_id:
            raise ModelAuthorityError(
                "accepted boundary contract group is owned by a foreign model"
            )
        signature = group.get("product_signature")
        if not isinstance(signature, Mapping):
            raise ModelAuthorityError(
                "accepted boundary contract group is missing its product signature"
            )
        if (
            str(signature.get("model_id") or "").strip() != contract.model_id
            or str(signature.get("interaction_group_id") or "").strip()
            != str(group.get("group_id") or "").strip()
        ):
            raise ModelAuthorityError(
                "accepted boundary contract product signature is foreign"
            )
    if set(contract.group_relation_ids) != group_ids:
        raise ModelAuthorityError(
            "accepted boundary contract relation map does not cover every group"
        )
    declared_relation_ids = {
        relation_id
        for relation_ids in contract.group_relation_ids.values()
        for relation_id in relation_ids
    }
    if not declared_relation_ids <= set(relation_by_id):
        raise ModelAuthorityError(
            "accepted boundary contract references an unmaterialized relation"
        )

    endpoint_refs = tuple(
        ref
        for ref in snapshot.owner_artifact_refs
        if ref.endpoint_kind == "boundary_contract"
    )
    if len(endpoint_refs) > 1:
        raise ModelAuthorityError(
            "snapshot may declare at most one boundary contract endpoint"
        )
    endpoint = endpoint_refs[0] if endpoint_refs else None
    if endpoint is None:
        if require_endpoint:
            raise ModelAuthorityError(
                "snapshot is missing the accepted boundary contract endpoint"
            )
    else:
        if (
            endpoint.endpoint_id != contract.contract_id
            or endpoint.fingerprint != contract.fingerprint
            or endpoint.owner_route != BOUNDARY_CONTRACT_OWNER_ROUTE
        ):
            raise ModelAuthorityError(
                "snapshot boundary contract endpoint is foreign or has the wrong owner"
            )

    validator_payload = {
        "schema": BOUNDARY_CONTRACT_VALIDATOR_SCHEMA,
        "owner_route": BOUNDARY_CONTRACT_OWNER_ROUTE,
        "endpoint": endpoint.to_dict() if endpoint is not None else None,
        "contract": contract.identity_payload(),
        "topology": {
            "fingerprint": topology_fingerprint,
            "relations": [
                relation.to_dict()
                for relation in sorted(
                    snapshot.relations,
                    key=lambda item: item.relation_id,
                )
            ],
        },
    }
    return canonical_fingerprint(validator_payload)


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
        / "models"
        / "authority"
        / "snapshots"
        / f"{digest}.json"
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    # Keep immutable artifacts byte-identical across Windows and POSIX.  Using
    # ``Path.write_text`` here lets Windows translate ``\n`` to CRLF, while
    # revision publication writes the same canonical JSON as UTF-8 bytes.  A
    # line-ending-only difference must not look like a conflicting
    # content-addressed object.
    payload = (
        json.dumps(
            snapshot.to_dict(),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")
    if target.exists():
        if target.read_bytes() != payload:
            raise ModelAuthorityError(
                "content-addressed snapshot path contains different bytes"
            )
        return target
    temporary = target.with_suffix(".json.tmp")
    temporary.write_bytes(payload)
    temporary.replace(target)
    return target


def write_content_addressed_boundary_contract(
    root: str | Path,
    contract: AcceptedBoundaryContract,
) -> Path:
    """Persist one accepted coupling denominator under the same authority.

    Writing this object does not move the project pointer.  A future accepted
    snapshot must reference the returned fingerprint through an
    ``AuthorityEndpointRef(endpoint_kind="boundary_contract")`` before any
    consumer can use it for a broad partitioned claim.
    """

    root_path = Path(root).resolve()
    digest = contract.fingerprint.split(":", 1)[1]
    target = (
        root_path
        / ".flowguard"
        / "models"
        / "authority"
        / MODEL_BOUNDARY_CONTRACT_ARTIFACT_CATEGORY
        / f"{digest}.json"
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = (
        json.dumps(
            contract.to_dict(),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")
    if target.exists():
        if target.read_bytes() != payload:
            raise ModelAuthorityError(
                "content-addressed boundary contract path contains different bytes"
            )
        return target
    temporary = target.with_suffix(".json.tmp")
    temporary.write_bytes(payload)
    temporary.replace(target)
    return target


def load_accepted_boundary_contract(
    path: str | Path,
) -> AcceptedBoundaryContract:
    """Load and revalidate one immutable accepted boundary contract."""

    try:
        payload = json.loads(
            Path(path).read_text(encoding="utf-8"),
            object_pairs_hook=_reject_duplicate_json_keys,
            parse_constant=lambda value: (_ for _ in ()).throw(
                ModelAuthorityError(f"non-finite JSON number: {value}")
            ),
        )
    except (OSError, json.JSONDecodeError, ModelAuthorityError) as exc:
        raise ModelAuthorityError(
            f"cannot load accepted boundary contract: {exc}"
        ) from exc
    return AcceptedBoundaryContract.from_dict(payload)


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
    "BOUNDARY_CONTRACT_OWNER_ROUTE",
    "BOUNDARY_CONTRACT_VALIDATOR_SCHEMA",
    "MODEL_BOUNDARY_CONTRACT_ARTIFACT_CATEGORY",
    "MODEL_BOUNDARY_CONTRACT_SCHEMA",
    "COVERAGE_DIMENSIONS",
    "BASE_COVERAGE_DIMENSIONS",
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
    "AcceptedBoundaryContract",
    "build_boundary_contract",
    "build_boundary_contract_from_snapshot",
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
    "boundary_topology_payload",
    "boundary_topology_fingerprint",
    "canonical_fingerprint",
    "canonical_json",
    "derive_affected_closure_fingerprint",
    "file_fingerprint",
    "load_model_system_snapshot",
    "load_accepted_boundary_contract",
    "validate_accepted_boundary_contract_for_snapshot",
    "validate_activation_plan",
    "validate_operational_rollback",
    "validate_revision_set_snapshots",
    "write_content_addressed_snapshot",
    "write_content_addressed_boundary_contract",
]
