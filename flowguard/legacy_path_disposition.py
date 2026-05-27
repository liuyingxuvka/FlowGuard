"""Legacy or alternate path disposition for model-miss closure."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from .export import to_jsonable
from .proof_artifact import ProofArtifactRef, coerce_proof_artifact_ref, proof_artifact_gap_codes


LEGACY_PATH_DELETED = "deleted"
LEGACY_PATH_BLOCKED = "blocked"
LEGACY_PATH_DELEGATED = "delegated_to_repaired_path"
LEGACY_PATH_SAME_CONTRACT_REPAIRED = "same_contract_repaired"
LEGACY_PATH_OUT_OF_SCOPE = "out_of_scope"
LEGACY_PATH_UNKNOWN = "unknown"

PASSING_LEGACY_PATH_DISPOSITIONS = {
    LEGACY_PATH_DELETED,
    LEGACY_PATH_BLOCKED,
    LEGACY_PATH_DELEGATED,
    LEGACY_PATH_SAME_CONTRACT_REPAIRED,
    LEGACY_PATH_OUT_OF_SCOPE,
}


def _as_tuple(values: Sequence[str] | None) -> tuple[str, ...]:
    if values is None:
        return ()
    return tuple(str(value) for value in values)


@dataclass(frozen=True)
class LegacyPathDisposition:
    """Disposition of an old or alternate path after a model-miss repair."""

    path_id: str
    disposition: str = LEGACY_PATH_UNKNOWN
    parent_entry_ids: tuple[str, ...] = ()
    repaired_contract_id: str = ""
    proof_artifact: ProofArtifactRef | Mapping[str, Any] | None = None
    in_scope: bool = True
    out_of_scope_reason: str = ""
    rationale: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "path_id", str(self.path_id))
        object.__setattr__(self, "disposition", str(self.disposition))
        object.__setattr__(self, "parent_entry_ids", _as_tuple(self.parent_entry_ids))
        object.__setattr__(self, "repaired_contract_id", str(self.repaired_contract_id))
        object.__setattr__(self, "proof_artifact", coerce_proof_artifact_ref(self.proof_artifact))
        object.__setattr__(self, "out_of_scope_reason", str(self.out_of_scope_reason))
        object.__setattr__(self, "rationale", str(self.rationale))
        object.__setattr__(self, "metadata", dict(self.metadata))

    def has_closing_disposition(self) -> bool:
        if self.disposition == LEGACY_PATH_OUT_OF_SCOPE:
            return bool(self.out_of_scope_reason)
        return self.disposition in PASSING_LEGACY_PATH_DISPOSITIONS

    def to_dict(self) -> dict[str, Any]:
        return {
            "path_id": self.path_id,
            "disposition": self.disposition,
            "parent_entry_ids": list(self.parent_entry_ids),
            "repaired_contract_id": self.repaired_contract_id,
            "proof_artifact": self.proof_artifact.to_dict() if self.proof_artifact else None,
            "in_scope": self.in_scope,
            "out_of_scope_reason": self.out_of_scope_reason,
            "rationale": self.rationale,
            "metadata": to_jsonable(dict(self.metadata)),
        }


@dataclass(frozen=True)
class LegacyPathDispositionFinding:
    """One gap in old-path model-miss closure."""

    code: str
    message: str
    path_id: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "code", str(self.code))
        object.__setattr__(self, "message", str(self.message))
        object.__setattr__(self, "path_id", str(self.path_id))
        object.__setattr__(self, "metadata", dict(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "path_id": self.path_id,
            "metadata": to_jsonable(dict(self.metadata)),
        }


@dataclass(frozen=True)
class LegacyPathDispositionReport:
    """Review result for legacy or alternate path closure."""

    ok: bool
    findings: tuple[LegacyPathDispositionFinding, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "findings", tuple(self.findings))

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "findings": [finding.to_dict() for finding in self.findings],
        }


def review_legacy_path_dispositions(
    dispositions: Sequence[LegacyPathDisposition],
    *,
    require_proof_artifacts: bool = False,
) -> LegacyPathDispositionReport:
    """Review whether old paths are closed, scoped out, or proof-backed."""

    findings: list[LegacyPathDispositionFinding] = []
    for disposition in dispositions:
        if not disposition.has_closing_disposition():
            findings.append(
                LegacyPathDispositionFinding(
                    "legacy_path_disposition_unknown",
                    "legacy path disposition is missing, unknown, or out-of-scope without reason",
                    path_id=disposition.path_id,
                    metadata=disposition.to_dict(),
                )
            )
            continue
        if require_proof_artifacts and disposition.disposition != LEGACY_PATH_OUT_OF_SCOPE:
            for code, message in proof_artifact_gap_codes(
                disposition.proof_artifact,
                require_external_scope=True,
                required_obligation_ids=(disposition.repaired_contract_id,),
                require_result_path=True,
                require_fingerprints=True,
            ):
                findings.append(
                    LegacyPathDispositionFinding(
                        f"legacy_path_{code}",
                        message,
                        path_id=disposition.path_id,
                        metadata=disposition.to_dict(),
                    )
                )
    return LegacyPathDispositionReport(ok=not findings, findings=tuple(findings))
