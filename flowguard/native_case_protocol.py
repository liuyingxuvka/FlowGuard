"""Strict native model/test case evidence.

This module is deliberately small and data-only.  A runner may register a
case in a model or a blueprint, but registration is not execution.  The only
passing result is a producer-written, raw-result-backed object whose owner,
source case, dimensions and oracle identities all match the frozen contract.
The protocol is also used by reuse: a current receipt with an old or missing
case projection is stale, never a passing shortcut.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Mapping, Sequence


NATIVE_CASE_PROTOCOL_SCHEMA = "flowguard.native_model_case_protocol.v1"
NATIVE_CASE_RESULT_SCHEMA = "flowguard.native_model_case_result.v1"
NATIVE_CASE_BINDING_SCHEMA = "flowguard.native_model_case_binding.v1"

GOOD_DIMENSIONS = (
    "input",
    "state",
    "output",
    "effect",
    "order",
    "completion",
)
BOUNDARY_DIMENSIONS = (
    "input",
    "error",
    "decision",
    "retry",
    "timeout",
    "completion",
)
BAD_DIMENSIONS = (
    "input",
    "state",
    "effect",
    "error",
    "decision",
    "completion",
)
CASE_DIMENSIONS = {
    "good": GOOD_DIMENSIONS,
    "boundary": BOUNDARY_DIMENSIONS,
    "bad": BAD_DIMENSIONS,
}
CASE_KINDS = frozenset((*CASE_DIMENSIONS, "aggregate"))
EVIDENCE_SCOPES = frozenset({"model_policy", "implementation_boundary"})
RESULT_OUTCOMES = frozenset({"pass", "fail", "rejected", "blocked", "not_run"})
_SHA256 = re.compile(r"^sha256:[0-9a-f]{64}$")


def _reject_duplicate_json_keys(
    pairs: list[tuple[str, object]],
) -> dict[str, object]:
    """Reject duplicate keys before a result envelope becomes evidence."""

    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise NativeCaseProtocolError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


class NativeCaseProtocolError(ValueError):
    """The native case contract/result cannot support a closure claim."""


@dataclass(frozen=True)
class NativeCaseBinding:
    """An exact source/native-to-blueprint case projection.

    A binding is deliberately not a string alias.  ``native_case_ids`` names
    the exact producer rows that must be present and pass before the
    ``blueprint_case_id`` is projected.  A row may therefore be consumed by a
    declared aggregate only when every listed child is present; missing,
    foreign, duplicate, or stale rows never create a projection.
    """

    owner_id: str
    blueprint_case_id: str
    blueprint_source_case_id: str
    native_case_ids: tuple[str, ...]
    case_kind: str
    evidence_scope: str
    covered_dimensions: tuple[str, ...]
    expected_status: str
    expected_observed_status: str = ""
    protected_failure_ids: tuple[str, ...] = ()
    expected_finding_codes: tuple[str, ...] = ()
    required_child_case_ids: tuple[str, ...] = ()
    required_trace_labels: tuple[str, ...] = ()
    mapping_fingerprint: str = ""

    def __post_init__(self) -> None:
        owner = _text(self.owner_id, field_name="owner_id")
        blueprint = _text(self.blueprint_case_id, field_name="blueprint_case_id")
        source = _text(self.blueprint_source_case_id, field_name="blueprint_source_case_id")
        kind = _text(self.case_kind, field_name="case_kind")
        if kind not in CASE_KINDS - {"aggregate"}:
            raise NativeCaseProtocolError(
                "native case binding case_kind must be a leaf kind: " + kind
            )
        native_ids = _ids(self.native_case_ids, field_name="native_case_ids")
        if not native_ids:
            raise NativeCaseProtocolError("native case binding requires native_case_ids")
        dimensions = _ids(self.covered_dimensions, field_name="covered_dimensions")
        expected_dimensions = CASE_DIMENSIONS[kind]
        if tuple(sorted(dimensions)) != tuple(sorted(expected_dimensions)):
            missing = sorted(set(expected_dimensions) - set(dimensions))
            extra = sorted(set(dimensions) - set(expected_dimensions))
            raise NativeCaseProtocolError(
                f"{kind} binding dimensions must be exact: missing={missing}, extra={extra}"
            )
        expected_status = _text(self.expected_status, field_name="expected_status")
        if expected_status not in {"pass", "rejected", "fail"}:
            raise NativeCaseProtocolError(
                "native case binding expected_status must be pass, rejected, or fail"
            )
        observed_status = self.expected_observed_status
        if observed_status:
            observed_status = _text(
                observed_status, field_name="expected_observed_status"
            )
        if self.evidence_scope not in EVIDENCE_SCOPES:
            raise NativeCaseProtocolError(
                "unsupported evidence_scope: " + str(self.evidence_scope)
            )
        object.__setattr__(self, "owner_id", owner)
        object.__setattr__(self, "blueprint_case_id", blueprint)
        object.__setattr__(self, "blueprint_source_case_id", source)
        object.__setattr__(self, "native_case_ids", native_ids)
        object.__setattr__(self, "case_kind", kind)
        object.__setattr__(self, "evidence_scope", _text(self.evidence_scope, field_name="evidence_scope"))
        object.__setattr__(self, "covered_dimensions", tuple(sorted(dimensions)))
        object.__setattr__(self, "expected_status", expected_status)
        object.__setattr__(self, "expected_observed_status", observed_status)
        object.__setattr__(
            self,
            "protected_failure_ids",
            _ids(self.protected_failure_ids, field_name="protected_failure_ids"),
        )
        object.__setattr__(
            self,
            "expected_finding_codes",
            _ids(self.expected_finding_codes, field_name="expected_finding_codes"),
        )
        object.__setattr__(
            self,
            "required_child_case_ids",
            _ids(self.required_child_case_ids, field_name="required_child_case_ids"),
        )
        object.__setattr__(
            self,
            "required_trace_labels",
            _ids(self.required_trace_labels, field_name="required_trace_labels"),
        )
        if self.mapping_fingerprint:
            object.__setattr__(
                self,
                "mapping_fingerprint",
                _fingerprint(self.mapping_fingerprint, field_name="mapping_fingerprint"),
            )

    @property
    def is_aggregate(self) -> bool:
        return len(self.native_case_ids) > 1 or bool(self.required_child_case_ids)

    @property
    def fingerprint(self) -> str:
        return fingerprint_payload(self.to_dict(include_fingerprint=False))

    def to_dict(self, *, include_fingerprint: bool = True) -> dict[str, Any]:
        payload = {
            "schema_version": NATIVE_CASE_BINDING_SCHEMA,
            "owner_id": self.owner_id,
            "blueprint_case_id": self.blueprint_case_id,
            "blueprint_source_case_id": self.blueprint_source_case_id,
            "native_case_ids": list(self.native_case_ids),
            "case_kind": self.case_kind,
            "evidence_scope": self.evidence_scope,
            "covered_dimensions": list(self.covered_dimensions),
            "expected_status": self.expected_status,
            "expected_observed_status": self.expected_observed_status,
            "protected_failure_ids": list(self.protected_failure_ids),
            "expected_finding_codes": list(self.expected_finding_codes),
            "required_child_case_ids": list(self.required_child_case_ids),
            "required_trace_labels": list(self.required_trace_labels),
            "mapping_fingerprint": self.mapping_fingerprint,
        }
        if include_fingerprint:
            payload["binding_fingerprint"] = self.fingerprint
        return payload


@dataclass(frozen=True)
class NativeBindingVerification:
    """Result of projecting exact native rows onto blueprint case IDs."""

    ok: bool
    projected_case_ids: tuple[str, ...] = ()
    missing_bindings: tuple[str, ...] = ()
    foreign_native_case_ids: tuple[str, ...] = ()
    duplicate_native_case_ids: tuple[str, ...] = ()
    findings: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": NATIVE_CASE_BINDING_SCHEMA,
            "ok": self.ok,
            "projected_case_ids": list(self.projected_case_ids),
            "missing_bindings": list(self.missing_bindings),
            "foreign_native_case_ids": list(self.foreign_native_case_ids),
            "duplicate_native_case_ids": list(self.duplicate_native_case_ids),
            "findings": list(self.findings),
        }


def _text(value: Any, *, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise NativeCaseProtocolError(f"{field_name} must be non-empty text")
    normalized = value.strip()
    if normalized != value:
        raise NativeCaseProtocolError(f"{field_name} must be normalized text")
    return normalized


def _ids(values: Sequence[Any] | None, *, field_name: str) -> tuple[str, ...]:
    if values is None:
        return ()
    if isinstance(values, (str, bytes)):
        raise NativeCaseProtocolError(f"{field_name} must be an array")
    result: list[str] = []
    for value in values:
        item = _text(value, field_name=field_name)
        if item in result:
            raise NativeCaseProtocolError(f"{field_name} contains a duplicate: {item}")
        result.append(item)
    return tuple(result)


def _fingerprint(value: Any, *, field_name: str) -> str:
    item = _text(value, field_name=field_name)
    if not _SHA256.fullmatch(item):
        raise NativeCaseProtocolError(f"{field_name} must be a canonical sha256 fingerprint")
    return item


def boundary_case_id(owner_id: str) -> str:
    """Return the stable boundary identity independent of runner content."""

    owner = _text(owner_id, field_name="owner_id")
    owner = owner.removeprefix("model:")
    return f"boundary:{owner}"


def qualified_case_id(owner_id: str, source_case_id: str) -> str:
    """Return the unambiguous reference used by cross-owner aggregates.

    Leaf case ids are intentionally owned by their producer.  An aggregate
    that consumes a case from another owner therefore cannot use a bare source
    id: two children may legitimately declare the same local case name.  The
    qualified form keeps the existing local ``required_child_case_ids`` wire
    compatible while giving recursive parents one exact, collision-free
    binding.  ``::`` is reserved as the owner/case separator and neither
    component is normalized or inferred here.
    """

    owner = _text(owner_id, field_name="owner_id")
    source = _text(source_case_id, field_name="source_case_id")
    return f"{owner}::{source}"


def fingerprint_payload(value: Any) -> str:
    """Compute the protocol's canonical content fingerprint."""

    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True)
class NativeModelCaseContract:
    """One planned native case or an explicit aggregate of child cases."""

    owner_id: str
    source_case_id: str
    case_kind: str
    protected_failure_ids: tuple[str, ...] = ()
    callable_ref: str = ""
    result_selector: str = ""
    expected_status: str = ""
    # The oracle outcome and the observed model status are distinct.  A
    # rejected/bad case can therefore have an expected outcome of
    # ``rejected`` while the model correctly reports a domain-specific
    # ``violation`` status.  Empty keeps the historical identity semantics
    # for contracts whose observed status equals their outcome.
    expected_observed_status: str = ""
    expected_finding_codes: tuple[str, ...] = ()
    covered_dimensions: tuple[str, ...] = ()
    oracle_member_ids: tuple[str, ...] = ()
    evidence_scope: str = ""
    required_child_case_ids: tuple[str, ...] = ()
    input_contract_fingerprint: str = ""
    oracle_content_fingerprint: str = ""

    def __post_init__(self) -> None:
        owner = _text(self.owner_id, field_name="owner_id")
        source = _text(self.source_case_id, field_name="source_case_id")
        kind = _text(self.case_kind, field_name="case_kind")
        if kind not in CASE_KINDS:
            raise NativeCaseProtocolError(f"unsupported case_kind: {kind}")
        if kind == "boundary" and source != boundary_case_id(owner):
            raise NativeCaseProtocolError(
                "boundary case id must be stable as boundary:<owner_without_model_prefix>"
            )
        object.__setattr__(self, "owner_id", owner)
        object.__setattr__(self, "source_case_id", source)
        object.__setattr__(self, "case_kind", kind)
        for name in ("protected_failure_ids", "expected_finding_codes", "oracle_member_ids", "required_child_case_ids"):
            object.__setattr__(self, name, _ids(getattr(self, name), field_name=name))
        object.__setattr__(self, "callable_ref", _text(self.callable_ref, field_name="callable_ref"))
        object.__setattr__(self, "result_selector", _text(self.result_selector, field_name="result_selector"))
        object.__setattr__(self, "evidence_scope", _text(self.evidence_scope, field_name="evidence_scope"))
        if self.evidence_scope not in EVIDENCE_SCOPES:
            raise NativeCaseProtocolError(f"unsupported evidence_scope: {self.evidence_scope}")
        expected = CASE_DIMENSIONS.get(kind, ())
        raw_dimensions = _ids(self.covered_dimensions, field_name="covered_dimensions")
        if kind == "aggregate":
            if not self.required_child_case_ids:
                raise NativeCaseProtocolError("aggregate case requires required_child_case_ids")
            if raw_dimensions:
                raise NativeCaseProtocolError("aggregate case cannot claim leaf dimensions")
        else:
            if tuple(sorted(raw_dimensions)) != tuple(sorted(expected)):
                missing = sorted(set(expected) - set(raw_dimensions))
                extra = sorted(set(raw_dimensions) - set(expected))
                raise NativeCaseProtocolError(
                    f"{kind} case dimensions must be exact: missing={missing}, extra={extra}"
                )
            if not self.oracle_member_ids:
                raise NativeCaseProtocolError("leaf case requires oracle_member_ids")
            if self.required_child_case_ids:
                raise NativeCaseProtocolError("leaf case cannot carry child case ids")
        object.__setattr__(self, "covered_dimensions", tuple(sorted(raw_dimensions)))
        if self.expected_status == "":
            if kind == "aggregate":
                expected_status = "pass"
            else:
                raise NativeCaseProtocolError("expected_status is required")
        else:
            expected_status = _text(self.expected_status, field_name="expected_status")
        object.__setattr__(self, "expected_status", expected_status)
        observed_status = self.expected_observed_status
        if observed_status:
            observed_status = _text(
                observed_status, field_name="expected_observed_status"
            )
        object.__setattr__(self, "expected_observed_status", observed_status)
        if self.input_contract_fingerprint:
            object.__setattr__(
                self,
                "input_contract_fingerprint",
                _fingerprint(self.input_contract_fingerprint, field_name="input_contract_fingerprint"),
            )
        if self.oracle_content_fingerprint:
            object.__setattr__(
                self,
                "oracle_content_fingerprint",
                _fingerprint(self.oracle_content_fingerprint, field_name="oracle_content_fingerprint"),
            )

    @property
    def is_aggregate(self) -> bool:
        return self.case_kind == "aggregate"

    @property
    def fingerprint(self) -> str:
        return fingerprint_payload(self.to_dict(include_fingerprint=False))

    def to_dict(self, *, include_fingerprint: bool = True) -> dict[str, Any]:
        payload = {
            "schema_version": NATIVE_CASE_PROTOCOL_SCHEMA,
            "owner_id": self.owner_id,
            "source_case_id": self.source_case_id,
            "case_kind": self.case_kind,
            "protected_failure_ids": list(self.protected_failure_ids),
            "callable_ref": self.callable_ref,
            "result_selector": self.result_selector,
            "expected_status": self.expected_status,
            "expected_observed_status": self.expected_observed_status,
            "expected_finding_codes": list(self.expected_finding_codes),
            "covered_dimensions": list(self.covered_dimensions),
            "oracle_member_ids": list(self.oracle_member_ids),
            "evidence_scope": self.evidence_scope,
            "required_child_case_ids": list(self.required_child_case_ids),
            "input_contract_fingerprint": self.input_contract_fingerprint,
            "oracle_content_fingerprint": self.oracle_content_fingerprint,
        }
        if include_fingerprint:
            payload["contract_fingerprint"] = self.fingerprint
        return payload


@dataclass(frozen=True)
class NativeModelCaseResult:
    """One producer-written result backed by an immutable raw artifact."""

    owner_id: str
    source_case_id: str
    outcome: str
    observed_status: str
    observed_finding_codes: tuple[str, ...] = ()
    executed_dimensions: tuple[str, ...] = ()
    oracle_results: tuple[Mapping[str, Any], ...] = ()
    result_artifact_fingerprint: str = ""
    input_fingerprint: str = ""
    model_fingerprint: str = ""
    code_fingerprint: str = ""
    test_fingerprint: str = ""
    oracle_fingerprint: str = ""
    toolchain_fingerprint: str = ""
    environment_fingerprint: str = ""
    raw_artifact_path: str = ""
    child_case_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for name in ("owner_id", "source_case_id", "outcome", "observed_status", "raw_artifact_path"):
            object.__setattr__(self, name, _text(getattr(self, name), field_name=name))
        if self.outcome not in RESULT_OUTCOMES:
            raise NativeCaseProtocolError(f"unsupported outcome: {self.outcome}")
        object.__setattr__(self, "observed_finding_codes", _ids(self.observed_finding_codes, field_name="observed_finding_codes"))
        object.__setattr__(self, "executed_dimensions", _ids(self.executed_dimensions, field_name="executed_dimensions"))
        object.__setattr__(self, "child_case_ids", _ids(self.child_case_ids, field_name="child_case_ids"))
        rows: list[Mapping[str, Any]] = []
        for row in self.oracle_results:
            if not isinstance(row, Mapping):
                raise NativeCaseProtocolError("oracle_results must contain objects")
            if set(row) - {"dimension", "oracle_member_id", "status", "ok", "finding_codes", "observed"}:
                raise NativeCaseProtocolError("oracle_results contains unknown fields")
            dimension = row.get("dimension")
            member = row.get("oracle_member_id")
            if not isinstance(dimension, str) or not dimension.strip() or not isinstance(member, str) or not member.strip():
                raise NativeCaseProtocolError("each oracle result requires dimension and oracle_member_id")
            rows.append(dict(row))
        dimensions = [str(row["dimension"]).strip() for row in rows]
        if len(dimensions) != len(set(dimensions)):
            raise NativeCaseProtocolError("oracle_results contain duplicate dimensions")
        object.__setattr__(self, "oracle_results", tuple(rows))
        object.__setattr__(self, "result_artifact_fingerprint", _fingerprint(self.result_artifact_fingerprint, field_name="result_artifact_fingerprint"))
        for name in (
            "input_fingerprint", "model_fingerprint", "code_fingerprint", "test_fingerprint",
            "oracle_fingerprint", "toolchain_fingerprint", "environment_fingerprint",
        ):
            object.__setattr__(self, name, _fingerprint(getattr(self, name), field_name=name))

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": NATIVE_CASE_RESULT_SCHEMA,
            "owner_id": self.owner_id,
            "source_case_id": self.source_case_id,
            "outcome": self.outcome,
            "observed_status": self.observed_status,
            "observed_finding_codes": list(self.observed_finding_codes),
            "executed_dimensions": list(self.executed_dimensions),
            "oracle_results": [dict(row) for row in self.oracle_results],
            "result_artifact_fingerprint": self.result_artifact_fingerprint,
            "input_fingerprint": self.input_fingerprint,
            "model_fingerprint": self.model_fingerprint,
            "code_fingerprint": self.code_fingerprint,
            "test_fingerprint": self.test_fingerprint,
            "oracle_fingerprint": self.oracle_fingerprint,
            "toolchain_fingerprint": self.toolchain_fingerprint,
            "environment_fingerprint": self.environment_fingerprint,
            "raw_artifact_path": self.raw_artifact_path,
            "child_case_ids": list(self.child_case_ids),
        }


@dataclass(frozen=True)
class NativeCaseVerification:
    """Deterministic comparison of frozen contracts and producer results."""

    ok: bool
    findings: tuple[str, ...] = ()
    missing_case_ids: tuple[str, ...] = ()
    foreign_case_ids: tuple[str, ...] = ()
    duplicate_case_ids: tuple[str, ...] = ()
    unasserted_dimensions: tuple[str, ...] = ()
    aggregate_case_ids: tuple[str, ...] = ()
    leaf_case_ids: tuple[str, ...] = ()
    model_policy_pass: bool = False
    implementation_boundary_pass: bool = False

    @property
    def status(self) -> str:
        return "pass" if self.ok else "blocked"

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": NATIVE_CASE_RESULT_SCHEMA,
            "ok": self.ok,
            "status": self.status,
            "findings": list(self.findings),
            "missing_case_ids": list(self.missing_case_ids),
            "foreign_case_ids": list(self.foreign_case_ids),
            "duplicate_case_ids": list(self.duplicate_case_ids),
            "unasserted_dimensions": list(self.unasserted_dimensions),
            "aggregate_case_ids": list(self.aggregate_case_ids),
            "leaf_case_ids": list(self.leaf_case_ids),
            "model_policy_pass": self.model_policy_pass,
            "implementation_boundary_pass": self.implementation_boundary_pass,
        }


def verify_native_model_cases(
    contracts: Sequence[NativeModelCaseContract],
    results: Sequence[NativeModelCaseResult],
    *,
    raw_artifact_root: str | Path | None = None,
    require_current_inputs: bool = True,
    available_case_keys: Sequence[str] | None = None,
) -> NativeCaseVerification:
    """Verify exact leaf/aggregate execution without alias or count inference."""

    contract_rows = tuple(contracts)
    result_rows = tuple(results)
    by_key: dict[tuple[str, str], NativeModelCaseContract] = {}
    findings: list[str] = []
    for contract in contract_rows:
        key = (contract.owner_id, contract.source_case_id)
        if key in by_key:
            findings.append(f"duplicate_contract:{contract.owner_id}:{contract.source_case_id}")
        by_key[key] = contract
    result_by_key: dict[tuple[str, str], NativeModelCaseResult] = {}
    duplicate: list[str] = []
    foreign: list[str] = []
    for result in result_rows:
        key = (result.owner_id, result.source_case_id)
        label = f"{result.owner_id}:{result.source_case_id}"
        if key in result_by_key:
            duplicate.append(label)
            continue
        result_by_key[key] = result
        if key not in by_key:
            foreign.append(label)
    missing = [
        f"{owner}:{case}"
        for owner, case in sorted(by_key)
        if (owner, case) not in result_by_key
    ]
    findings.extend(f"foreign_case:{item}" for item in sorted(foreign))
    findings.extend(f"duplicate_case:{item}" for item in sorted(duplicate))
    findings.extend(f"missing_case:{item}" for item in missing)
    root = Path(raw_artifact_root).resolve() if raw_artifact_root is not None else None
    available_keys = {
        str(item)
        for item in (available_case_keys or ())
        if isinstance(item, str) and item
    }
    unasserted: list[str] = []
    model_policy_seen = False
    model_policy_ok = True
    implementation_seen = False
    implementation_ok = True
    aggregates: list[str] = []
    leaves: list[str] = []
    for key, contract in sorted(by_key.items()):
        result = result_by_key.get(key)
        if result is None:
            continue
        label = f"{contract.owner_id}:{contract.source_case_id}"
        if root is not None:
            raw_artifact = Path(result.raw_artifact_path).expanduser()
            if not raw_artifact.is_absolute():
                raw_artifact = root / raw_artifact
            # Check the link before resolving it.  Resolving first would make
            # a symlink to an otherwise valid file look like an ordinary file
            # and would let evidence escape the producer-owned directory.
            if raw_artifact.is_symlink():
                findings.append(f"raw_artifact_missing:{label}")
            else:
                artifact = raw_artifact.resolve()
                if not artifact.is_file() or root not in artifact.parents:
                    findings.append(f"raw_artifact_missing:{label}")
                else:
                    digest = "sha256:" + hashlib.sha256(artifact.read_bytes()).hexdigest()
                    if digest != result.result_artifact_fingerprint:
                        findings.append(f"raw_artifact_fingerprint_mismatch:{label}")
        if contract.is_aggregate:
            aggregates.append(label)
            expected_children = set(contract.required_child_case_ids)
            actual_children = set(result.child_case_ids)
            if expected_children != actual_children:
                findings.append(f"aggregate_children_mismatch:{label}")
            missing_children = []
            for child_id in sorted(expected_children):
                references = {child_id}
                if "::" not in child_id:
                    references.add(qualified_case_id(contract.owner_id, child_id))
                if (
                    (contract.owner_id, child_id) not in result_by_key
                    and not (references & available_keys)
                ):
                    missing_children.append(child_id)
            if missing_children:
                findings.append(
                    f"aggregate_child_result_missing:{label}:{','.join(missing_children)}"
                )
            if result.outcome != contract.expected_status:
                findings.append(f"aggregate_status_mismatch:{label}")
            continue
        leaves.append(label)
        expected_dimensions = set(contract.covered_dimensions)
        observed_dimensions = set(result.executed_dimensions)
        missing_dimensions = sorted(expected_dimensions - observed_dimensions)
        extra_dimensions = sorted(observed_dimensions - expected_dimensions)
        if missing_dimensions:
            unasserted.extend(f"{label}:{dimension}" for dimension in missing_dimensions)
        if extra_dimensions:
            findings.append(
                f"unexpected_dimension:{label}:{','.join(extra_dimensions)}"
            )
        oracle_dimensions = {
            str(row.get("dimension", "")).strip()
            for row in result.oracle_results
            if isinstance(row, Mapping)
        }
        if oracle_dimensions != observed_dimensions:
            findings.append(f"oracle_dimension_mismatch:{label}")
        expected_oracle_members = set(contract.oracle_member_ids)
        observed_oracle_members = {
            str(row.get("oracle_member_id", "")).strip()
            for row in result.oracle_results
            if isinstance(row, Mapping)
        }
        if observed_oracle_members != expected_oracle_members:
            findings.append(f"oracle_member_mismatch:{label}")
        for row in result.oracle_results:
            if not isinstance(row, Mapping):
                continue
            if "ok" not in row or not isinstance(row.get("ok"), bool):
                findings.append(f"oracle_ok_not_boolean:{label}")
            if "status" not in row or not isinstance(row.get("status"), str) or not str(row.get("status", "")).strip():
                findings.append(f"oracle_status_missing:{label}")
        if result.outcome != contract.expected_status:
            findings.append(f"status_mismatch:{label}")
        expected_observed_status = (
            contract.expected_observed_status or contract.expected_status
        )
        if result.observed_status != expected_observed_status:
            findings.append(f"observed_status_mismatch:{label}")
        expected_findings = set(contract.expected_finding_codes)
        if not expected_findings.issubset(set(result.observed_finding_codes)):
            findings.append(f"finding_code_missing:{label}")
        if contract.input_contract_fingerprint and result.input_fingerprint != contract.input_contract_fingerprint:
            findings.append(f"input_contract_fingerprint_mismatch:{label}")
        if contract.oracle_content_fingerprint and result.oracle_fingerprint != contract.oracle_content_fingerprint:
            findings.append(f"oracle_content_fingerprint_mismatch:{label}")
        if result.outcome in {"pass", "rejected"} and missing_dimensions:
            findings.append(f"unasserted_dimension:{label}")
        if require_current_inputs and any(
            not getattr(result, name)
            for name in (
                "input_fingerprint", "model_fingerprint", "code_fingerprint", "test_fingerprint",
                "oracle_fingerprint", "toolchain_fingerprint", "environment_fingerprint",
            )
        ):
            findings.append(f"current_input_fingerprint_missing:{label}")
        if contract.evidence_scope == "model_policy":
            model_policy_seen = True
            model_policy_ok = model_policy_ok and result.outcome == contract.expected_status
        elif contract.evidence_scope == "implementation_boundary":
            implementation_seen = True
            implementation_ok = implementation_ok and result.outcome == contract.expected_status
    if unasserted:
        findings.extend(f"unasserted_dimension:{item}" for item in sorted(set(unasserted)))
    ok = not findings and bool(contract_rows) and bool(result_rows)
    model_policy = model_policy_seen and model_policy_ok and not findings
    implementation = implementation_seen and implementation_ok and not findings
    # A policy-model result cannot silently become an implementation claim.
    if model_policy and not implementation_seen:
        implementation = False
    return NativeCaseVerification(
        ok=ok,
        findings=tuple(dict.fromkeys(sorted(findings))),
        missing_case_ids=tuple(missing),
        foreign_case_ids=tuple(sorted(foreign)),
        duplicate_case_ids=tuple(sorted(duplicate)),
        unasserted_dimensions=tuple(sorted(set(unasserted))),
        aggregate_case_ids=tuple(aggregates),
        leaf_case_ids=tuple(leaves),
        model_policy_pass=model_policy,
        implementation_boundary_pass=implementation,
    )


def verify_native_case_bindings(
    bindings: Sequence[NativeCaseBinding],
    results: Sequence[NativeModelCaseResult],
    *,
    mapping_fingerprint: str | None = None,
) -> NativeBindingVerification:
    """Verify an exact native-to-blueprint projection.

    This is intentionally a separate gate from :func:`verify_native_model_cases`.
    The latter proves a producer row against its native contract; this function
    proves that the *same* rows are sufficient to project a blueprint case.
    There is no suffix, count, fuzzy, or alias matching: every native row must
    be named by at least one binding and every binding must name every required
    row.  Multiple exact blueprint obligations may intentionally consume the
    same producer row; each such projection is still checked independently.
    A binding is projected only after all of its rows and all of its oracle
    dimensions pass.  Aggregate bindings additionally require the exact child
    set declared by the binding.
    """

    binding_rows = tuple(bindings)
    result_rows = tuple(results)
    findings: list[str] = []
    by_blueprint: dict[str, NativeCaseBinding] = {}
    # A single current producer row may be consumed by several exact
    # blueprint obligations.  Keep the reverse index as a set so intentional
    # reuse does not become a duplicate/foreign failure; each binding still
    # validates the row independently below.
    native_to_blueprint: dict[tuple[str, str], set[str]] = {}
    duplicate_blueprints: set[str] = set()
    duplicate_native: set[str] = set()

    expected_mapping_fp = ""
    if mapping_fingerprint:
        expected_mapping_fp = _fingerprint(
            mapping_fingerprint, field_name="mapping_fingerprint"
        )

    for binding in binding_rows:
        if not isinstance(binding, NativeCaseBinding):
            findings.append("binding_not_typed")
            continue
        blueprint_key = binding.blueprint_case_id
        if blueprint_key in by_blueprint:
            duplicate_blueprints.add(blueprint_key)
        else:
            by_blueprint[blueprint_key] = binding
        if expected_mapping_fp and binding.mapping_fingerprint != expected_mapping_fp:
            findings.append(
                f"mapping_fingerprint_mismatch:{binding.owner_id}:{blueprint_key}"
            )
        for native_id in binding.native_case_ids:
            native_key = (binding.owner_id, native_id)
            native_label = f"{binding.owner_id}:{native_id}"
            native_to_blueprint.setdefault(native_key, set()).add(blueprint_key)

    findings.extend(f"duplicate_binding:{item}" for item in sorted(duplicate_blueprints))
    findings.extend(f"duplicate_native_binding:{item}" for item in sorted(duplicate_native))

    result_by_key: dict[tuple[str, str], NativeModelCaseResult] = {}
    duplicate_results: set[str] = set()
    for result in result_rows:
        if not isinstance(result, NativeModelCaseResult):
            findings.append("native_result_not_typed")
            continue
        key = (result.owner_id, result.source_case_id)
        label = f"{result.owner_id}:{result.source_case_id}"
        if key in result_by_key:
            duplicate_results.add(label)
            continue
        result_by_key[key] = result
        if key not in native_to_blueprint:
            findings.append(f"foreign_native_case:{label}")
    findings.extend(f"duplicate_native_result:{item}" for item in sorted(duplicate_results))

    missing_bindings: list[str] = []
    projected: list[str] = []
    declared_native = set(native_to_blueprint)
    for blueprint_key, binding in sorted(by_blueprint.items()):
        binding_label = f"{binding.owner_id}:{blueprint_key}"
        required_keys = tuple((binding.owner_id, item) for item in binding.native_case_ids)
        missing_keys = [
            f"{owner}:{source}"
            for owner, source in required_keys
            if (owner, source) not in result_by_key
        ]
        if missing_keys:
            missing_bindings.append(blueprint_key)
            findings.append(
                f"binding_native_result_missing:{binding_label}:{','.join(sorted(missing_keys))}"
            )
            continue

        binding_failed = False
        expected_observed_status = (
            binding.expected_observed_status or binding.expected_status
        )
        expected_dimensions = set(binding.covered_dimensions)
        expected_findings = set(binding.expected_finding_codes)
        for native_key in required_keys:
            result = result_by_key[native_key]
            native_label = f"{result.owner_id}:{result.source_case_id}"
            if result.outcome != binding.expected_status:
                findings.append(f"binding_outcome_mismatch:{binding_label}:{native_label}")
                binding_failed = True
            if result.observed_status != expected_observed_status:
                findings.append(f"binding_observed_status_mismatch:{binding_label}:{native_label}")
                binding_failed = True
            if expected_findings and not expected_findings.issubset(
                set(result.observed_finding_codes)
            ):
                findings.append(f"binding_finding_code_missing:{binding_label}:{native_label}")
                binding_failed = True
            if binding.protected_failure_ids and not set(binding.protected_failure_ids).issubset(
                set(result.observed_finding_codes)
            ):
                findings.append(f"binding_protected_failure_missing:{binding_label}:{native_label}")
                binding_failed = True
            observed_dimensions = set(result.executed_dimensions)
            if observed_dimensions != expected_dimensions:
                missing = sorted(expected_dimensions - observed_dimensions)
                extra = sorted(observed_dimensions - expected_dimensions)
                findings.append(
                    f"binding_dimensions_mismatch:{binding_label}:{native_label}:"
                    f"missing={','.join(missing)}:extra={','.join(extra)}"
                )
                binding_failed = True
            oracle_dimensions = {
                str(row.get("dimension", "")).strip()
                for row in result.oracle_results
                if isinstance(row, Mapping)
            }
            if oracle_dimensions != expected_dimensions:
                findings.append(f"binding_oracle_dimensions_mismatch:{binding_label}:{native_label}")
                binding_failed = True
            for row in result.oracle_results:
                if not isinstance(row, Mapping):
                    binding_failed = True
                    continue
                if not isinstance(row.get("ok"), bool) or not row.get("ok"):
                    findings.append(f"binding_oracle_not_passing:{binding_label}:{native_label}")
                    binding_failed = True
                status = row.get("status")
                if not isinstance(status, str) or not status.strip():
                    findings.append(f"binding_oracle_status_missing:{binding_label}:{native_label}")
                    binding_failed = True
            if result.outcome in {"not_run", "blocked", "fail"}:
                binding_failed = True

            if binding.required_child_case_ids:
                actual_children = set(result.child_case_ids)
                expected_children = set(binding.required_child_case_ids)
                if actual_children != expected_children:
                    findings.append(f"binding_children_mismatch:{binding_label}:{native_label}")
                    binding_failed = True
                for child_id in sorted(expected_children):
                    if "::" in child_id:
                        child_owner, child_source = child_id.split("::", 1)
                        child_key = (child_owner, child_source)
                    else:
                        child_key = (binding.owner_id, child_id)
                    # A declared binding is only a mapping declaration.  It
                    # does not prove that the child was actually produced.
                    # Require the concrete result row here; otherwise an
                    # aggregate could project itself from a list of planned
                    # children while one or more leaves never ran.
                    if child_key not in result_by_key:
                        findings.append(
                            f"binding_child_result_missing:{binding_label}:{child_id}"
                        )
                        binding_failed = True

        if not binding_failed:
            projected.append(blueprint_key)

    ok = bool(binding_rows) and not findings and not missing_bindings
    return NativeBindingVerification(
        ok=ok,
        projected_case_ids=tuple(sorted(projected)),
        missing_bindings=tuple(sorted(set(missing_bindings))),
        foreign_native_case_ids=tuple(
            sorted(
                f"{owner}:{source}"
                for owner, source in result_by_key
                if (owner, source) not in declared_native
            )
        ),
        duplicate_native_case_ids=tuple(sorted(set(duplicate_results) | duplicate_native)),
        findings=tuple(dict.fromkeys(sorted(findings))),
    )


def load_native_model_case_results(path: str | Path) -> tuple[NativeModelCaseResult, ...]:
    """Load only the current strict result envelope; never infer from text."""

    result_path = Path(path).expanduser().resolve()
    if result_path.is_symlink() or not result_path.is_file():
        raise NativeCaseProtocolError("native result artifact is missing or a symlink")
    try:
        payload = json.loads(
            result_path.read_text(encoding="utf-8"),
            object_pairs_hook=_reject_duplicate_json_keys,
            parse_constant=lambda item: (_ for _ in ()).throw(
                NativeCaseProtocolError(f"non-finite JSON number: {item}")
            ),
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise NativeCaseProtocolError(f"native result artifact is unreadable: {exc}") from exc
    if isinstance(payload, Mapping):
        if set(payload) != {"schema_version", "results"} or payload.get("schema_version") != NATIVE_CASE_RESULT_SCHEMA:
            raise NativeCaseProtocolError("native result artifact envelope is not current")
        raw_rows = payload["results"]
    else:
        raise NativeCaseProtocolError("native result artifact must be an envelope object")
    if not isinstance(raw_rows, list):
        raise NativeCaseProtocolError("native result artifact results must be an array")
    rows = []
    for index, raw in enumerate(raw_rows):
        if not isinstance(raw, Mapping):
            raise NativeCaseProtocolError("native result row must be an object")
        row_payload = dict(raw)
        row_schema = row_payload.pop("schema_version", None)
        if row_schema != NATIVE_CASE_RESULT_SCHEMA:
            raise NativeCaseProtocolError(
                f"native result row {index} envelope schema is not current"
            )
        try:
            rows.append(NativeModelCaseResult(**row_payload))
        except (NativeCaseProtocolError, TypeError, ValueError) as exc:
            raise NativeCaseProtocolError(
                f"native result row {index} is invalid: {exc}"
            ) from exc
    return tuple(rows)


__all__ = [
    "BAD_DIMENSIONS",
    "BOUNDARY_DIMENSIONS",
    "CASE_DIMENSIONS",
    "CASE_KINDS",
    "EVIDENCE_SCOPES",
    "GOOD_DIMENSIONS",
    "NATIVE_CASE_PROTOCOL_SCHEMA",
    "NATIVE_CASE_BINDING_SCHEMA",
    "NATIVE_CASE_RESULT_SCHEMA",
    "NativeCaseBinding",
    "NativeBindingVerification",
    "NativeCaseProtocolError",
    "NativeCaseVerification",
    "NativeModelCaseContract",
    "NativeModelCaseResult",
    "boundary_case_id",
    "fingerprint_payload",
    "load_native_model_case_results",
    "qualified_case_id",
    "verify_native_model_cases",
    "verify_native_case_bindings",
]
