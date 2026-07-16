"""Fail-closed purpose closure for one concrete FlowGuard model instance.

The reusable model type is not assigned one permanent purpose.  Each concrete
instance freezes a task-specific declaration before candidate construction,
then binds the resulting candidate and its native good/bad proof surface.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Mapping, Sequence


PURPOSE_CLOSURE_SCHEMA = "flowguard.model_purpose_closure.v1"
DECLARATION_PHASE = "before_candidate"
CURRENT_ADOPTION_SCOPE = "current_candidate_only"
_ID_RE = re.compile(r"^[a-z0-9][a-z0-9._:/-]*$")
_SHA_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_PLACEHOLDERS = {
    "purpose",
    "model purpose",
    "todo",
    "tbd",
    "unknown",
    "generic failure",
    "something wrong",
    "test",
}


class ModelPurposeError(ValueError):
    """Raised when a purpose closure is absent, stale, or disconnected."""


def canonical_fingerprint(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def file_fingerprint(path: str | Path) -> str:
    return f"sha256:{hashlib.sha256(Path(path).read_bytes()).hexdigest()}"


def _clean_id(value: Any, field_name: str) -> str:
    result = str(value or "").strip()
    if not _ID_RE.fullmatch(result):
        raise ModelPurposeError(f"{field_name} must be a stable lowercase id")
    return result


def _clean_text(value: Any, field_name: str, *, minimum: int = 24) -> str:
    result = " ".join(str(value or "").split())
    if len(result) < minimum or result.casefold() in _PLACEHOLDERS:
        raise ModelPurposeError(f"{field_name} must be reviewable and non-placeholder")
    return result


@dataclass(frozen=True)
class FailureProofBinding:
    failure_id: str
    known_bad_case_id: str
    oracle_id: str

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "FailureProofBinding":
        unknown = set(payload) - {"failure_id", "known_bad_case_id", "oracle_id"}
        if unknown:
            raise ModelPurposeError(f"unknown failure binding fields: {sorted(unknown)}")
        return cls(
            failure_id=_clean_id(payload.get("failure_id"), "failure_id"),
            known_bad_case_id=_clean_id(payload.get("known_bad_case_id"), "known_bad_case_id"),
            oracle_id=_clean_id(payload.get("oracle_id"), "oracle_id"),
        )

    def to_dict(self) -> dict[str, str]:
        return {
            "failure_id": self.failure_id,
            "known_bad_case_id": self.known_bad_case_id,
            "oracle_id": self.oracle_id,
        }


@dataclass(frozen=True)
class ModelPurposeClosure:
    model_instance_id: str
    reusable_model_type_id: str
    task_intent_id: str
    guarded_purpose: str
    protected_failure_ids: tuple[str, ...]
    known_good_case_id: str
    failure_bindings: tuple[FailureProofBinding, ...]
    claim_boundary: str
    evidence_check_ids: tuple[str, ...]
    model_sha256: str
    runner_sha256: str
    declaration_fingerprint: str
    closure_fingerprint: str
    declaration_phase: str = DECLARATION_PHASE
    adoption_scope: str = CURRENT_ADOPTION_SCOPE
    schema_version: str = PURPOSE_CLOSURE_SCHEMA

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "ModelPurposeClosure":
        allowed = {
            "schema_version", "model_instance_id", "reusable_model_type_id", "task_intent_id",
            "declaration_phase", "guarded_purpose", "protected_failure_ids", "known_good_case_id",
            "failure_bindings", "claim_boundary", "evidence_check_ids", "adoption_scope",
            "model_sha256", "runner_sha256", "declaration_fingerprint", "closure_fingerprint",
        }
        unknown = set(payload) - allowed
        if unknown:
            raise ModelPurposeError(f"unknown purpose closure fields: {sorted(unknown)}")
        if payload.get("schema_version") != PURPOSE_CLOSURE_SCHEMA:
            raise ModelPurposeError("unsupported purpose closure schema")
        if payload.get("declaration_phase") != DECLARATION_PHASE:
            raise ModelPurposeError("purpose must be frozen before candidate construction")
        if payload.get("adoption_scope") != CURRENT_ADOPTION_SCOPE:
            raise ModelPurposeError("purpose closure must use current-candidate-only adoption scope")
        protected = tuple(_clean_id(item, "protected_failure_id") for item in payload.get("protected_failure_ids", ()))
        if not protected:
            raise ModelPurposeError("at least one protected_failure_id is required")
        if len(protected) != len(set(protected)):
            raise ModelPurposeError("protected_failure_ids must be unique")
        bindings = tuple(FailureProofBinding.from_dict(item) for item in payload.get("failure_bindings", ()))
        if len(bindings) != len(protected):
            raise ModelPurposeError("each protected failure requires exactly one known-bad binding")
        if tuple(item.failure_id for item in bindings) != protected:
            raise ModelPurposeError("failure bindings must exactly match protected_failure_ids in order")
        bad_case_ids = tuple(item.known_bad_case_id for item in bindings)
        if len(bad_case_ids) != len(set(bad_case_ids)):
            raise ModelPurposeError("known-bad case ids must be unique per protected failure")
        evidence = tuple(_clean_id(item, "evidence_check_id") for item in payload.get("evidence_check_ids", ()))
        if not evidence:
            raise ModelPurposeError("at least one native evidence check is required")
        model_sha = str(payload.get("model_sha256", ""))
        runner_sha = str(payload.get("runner_sha256", ""))
        if not _SHA_RE.fullmatch(model_sha) or not _SHA_RE.fullmatch(runner_sha):
            raise ModelPurposeError("model and runner fingerprints must be lowercase sha256 identities")
        result = cls(
            model_instance_id=_clean_id(payload.get("model_instance_id"), "model_instance_id"),
            reusable_model_type_id=_clean_id(payload.get("reusable_model_type_id"), "reusable_model_type_id"),
            task_intent_id=_clean_id(payload.get("task_intent_id"), "task_intent_id"),
            guarded_purpose=_clean_text(payload.get("guarded_purpose"), "guarded_purpose"),
            protected_failure_ids=protected,
            known_good_case_id=_clean_id(payload.get("known_good_case_id"), "known_good_case_id"),
            failure_bindings=bindings,
            claim_boundary=_clean_text(payload.get("claim_boundary"), "claim_boundary", minimum=40),
            evidence_check_ids=evidence,
            model_sha256=model_sha,
            runner_sha256=runner_sha,
            declaration_fingerprint=str(payload.get("declaration_fingerprint", "")),
            closure_fingerprint=str(payload.get("closure_fingerprint", "")),
        )
        if result.declaration_fingerprint != canonical_fingerprint(result.declaration_payload()):
            raise ModelPurposeError("stale or invalid declaration_fingerprint")
        if result.closure_fingerprint != canonical_fingerprint(result.closure_payload()):
            raise ModelPurposeError("stale or invalid closure_fingerprint")
        return result

    def declaration_payload(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "model_instance_id": self.model_instance_id,
            "reusable_model_type_id": self.reusable_model_type_id,
            "task_intent_id": self.task_intent_id,
            "declaration_phase": self.declaration_phase,
            "guarded_purpose": self.guarded_purpose,
            "protected_failure_ids": list(self.protected_failure_ids),
            "claim_boundary": self.claim_boundary,
            "adoption_scope": self.adoption_scope,
        }

    def closure_payload(self) -> dict[str, Any]:
        return {
            **self.declaration_payload(),
            "known_good_case_id": self.known_good_case_id,
            "failure_bindings": [item.to_dict() for item in self.failure_bindings],
            "evidence_check_ids": list(self.evidence_check_ids),
            "model_sha256": self.model_sha256,
            "runner_sha256": self.runner_sha256,
            "declaration_fingerprint": self.declaration_fingerprint,
        }

    def validate_current_files(self, root: str | Path, *, model_path: str, runner_path: str) -> None:
        root_path = Path(root).resolve()
        if file_fingerprint(root_path / model_path) != self.model_sha256:
            raise ModelPurposeError("model candidate fingerprint is stale")
        if file_fingerprint(root_path / runner_path) != self.runner_sha256:
            raise ModelPurposeError("native runner fingerprint is stale")

    def to_dict(self) -> dict[str, Any]:
        return {**self.closure_payload(), "closure_fingerprint": self.closure_fingerprint}


def build_model_purpose_closure(
    *, model_instance_id: str, reusable_model_type_id: str, task_intent_id: str,
    guarded_purpose: str, protected_failure_ids: Sequence[str], known_good_case_id: str,
    failure_bindings: Sequence[Mapping[str, Any] | FailureProofBinding], claim_boundary: str,
    evidence_check_ids: Sequence[str], model_sha256: str, runner_sha256: str,
) -> ModelPurposeClosure:
    declaration = {
        "schema_version": PURPOSE_CLOSURE_SCHEMA,
        "model_instance_id": model_instance_id,
        "reusable_model_type_id": reusable_model_type_id,
        "task_intent_id": task_intent_id,
        "declaration_phase": DECLARATION_PHASE,
        "guarded_purpose": guarded_purpose,
        "protected_failure_ids": list(protected_failure_ids),
        "claim_boundary": claim_boundary,
        "adoption_scope": CURRENT_ADOPTION_SCOPE,
    }
    binding_payloads = [item.to_dict() if isinstance(item, FailureProofBinding) else dict(item) for item in failure_bindings]
    payload = {
        **declaration,
        "known_good_case_id": known_good_case_id,
        "failure_bindings": binding_payloads,
        "evidence_check_ids": list(evidence_check_ids),
        "model_sha256": model_sha256,
        "runner_sha256": runner_sha256,
        "declaration_fingerprint": canonical_fingerprint(declaration),
    }
    payload["closure_fingerprint"] = canonical_fingerprint(payload)
    return ModelPurposeClosure.from_dict(payload)


def validate_unique_model_instances(closures: Sequence[ModelPurposeClosure]) -> None:
    ids = [item.model_instance_id for item in closures]
    duplicates = sorted({item for item in ids if ids.count(item) > 1})
    if duplicates:
        raise ModelPurposeError(f"duplicate model_instance_id: {duplicates}")


__all__ = [
    "CURRENT_ADOPTION_SCOPE", "DECLARATION_PHASE", "PURPOSE_CLOSURE_SCHEMA",
    "FailureProofBinding", "ModelPurposeClosure", "ModelPurposeError",
    "build_model_purpose_closure", "canonical_fingerprint", "file_fingerprint",
    "validate_unique_model_instances",
]
