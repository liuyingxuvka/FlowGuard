"""Shared proof artifact references for FlowGuard evidence consumers.

Review helpers do not execute project commands. They consume proof artifact
references produced by command runners, replay adapters, or project-specific
evidence collectors and decide whether a confidence claim is supported by a
fresh external artifact instead of a caller-declared status string alone.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from .export import to_jsonable


PROOF_ARTIFACT_STATUS_PASSED = "passed"
PROOF_ARTIFACT_STATUS_FAILED = "failed"
PROOF_ARTIFACT_STATUS_SKIPPED = "skipped"
PROOF_ARTIFACT_STATUS_STALE = "stale"
PROOF_ARTIFACT_STATUS_NOT_RUN = "not_run"
PROOF_ARTIFACT_STATUS_RUNNING = "running"
PROOF_ARTIFACT_STATUS_PROGRESS_ONLY = "progress_only"
PROOF_ARTIFACT_STATUS_ERROR = "error"

PROOF_ARTIFACT_SCOPE_EXTERNAL_CONTRACT = "external_contract"
PROOF_ARTIFACT_SCOPE_INTERNAL_PATH = "internal_path"
PROOF_ARTIFACT_SCOPE_MIXED = "mixed"
PROOF_ARTIFACT_SCOPE_UNKNOWN = "unknown"

PASSING_PROOF_ARTIFACT_STATUSES = {PROOF_ARTIFACT_STATUS_PASSED}
NON_PASSING_PROOF_ARTIFACT_STATUSES = {
    PROOF_ARTIFACT_STATUS_FAILED,
    PROOF_ARTIFACT_STATUS_SKIPPED,
    PROOF_ARTIFACT_STATUS_STALE,
    PROOF_ARTIFACT_STATUS_NOT_RUN,
    PROOF_ARTIFACT_STATUS_RUNNING,
    PROOF_ARTIFACT_STATUS_PROGRESS_ONLY,
    PROOF_ARTIFACT_STATUS_ERROR,
}
EXTERNAL_PROOF_ARTIFACT_SCOPES = {
    PROOF_ARTIFACT_SCOPE_EXTERNAL_CONTRACT,
    PROOF_ARTIFACT_SCOPE_MIXED,
}


def _as_tuple(values: Sequence[str] | None) -> tuple[str, ...]:
    if values is None:
        return ()
    return tuple(str(value) for value in values)


def _as_str_map(values: Mapping[str, Any] | None) -> dict[str, str]:
    if not values:
        return {}
    return {str(key): str(value) for key, value in values.items()}


@dataclass(frozen=True)
class ProofArtifactRef:
    """One concrete proof artifact produced by a validation command or replay."""

    artifact_id: str
    producer_route: str = ""
    command: str = ""
    result_path: str = ""
    result_status: str = PROOF_ARTIFACT_STATUS_NOT_RUN
    exit_code: int | None = None
    started_at: str = ""
    finished_at: str = ""
    artifact_fingerprints: Mapping[str, str] = field(default_factory=dict)
    covered_obligation_ids: tuple[str, ...] = ()
    assertion_scope: str = PROOF_ARTIFACT_SCOPE_EXTERNAL_CONTRACT
    current: bool = True
    route_evidence_current: bool = True
    progress_only: bool = False
    stale_reasons: tuple[str, ...] = ()
    route_gap_codes: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "artifact_id", str(self.artifact_id))
        object.__setattr__(self, "producer_route", str(self.producer_route))
        object.__setattr__(self, "command", str(self.command))
        object.__setattr__(self, "result_path", str(self.result_path))
        object.__setattr__(self, "result_status", str(self.result_status))
        object.__setattr__(self, "started_at", str(self.started_at))
        object.__setattr__(self, "finished_at", str(self.finished_at))
        object.__setattr__(self, "artifact_fingerprints", _as_str_map(self.artifact_fingerprints))
        object.__setattr__(self, "covered_obligation_ids", _as_tuple(self.covered_obligation_ids))
        object.__setattr__(self, "assertion_scope", str(self.assertion_scope))
        object.__setattr__(self, "stale_reasons", _as_tuple(self.stale_reasons))
        object.__setattr__(self, "route_gap_codes", _as_tuple(self.route_gap_codes))
        object.__setattr__(self, "metadata", dict(self.metadata))

    def has_external_scope(self) -> bool:
        return self.assertion_scope in EXTERNAL_PROOF_ARTIFACT_SCOPES

    def has_current_pass(self) -> bool:
        return (
            self.result_status in PASSING_PROOF_ARTIFACT_STATUSES
            and self.current
            and self.route_evidence_current
            and not self.progress_only
            and not self.stale_reasons
            and not self.route_gap_codes
            and self.exit_code in (None, 0)
        )

    def covers_any(self, obligation_ids: Sequence[str]) -> bool:
        required = {str(value) for value in obligation_ids if str(value)}
        if not required:
            return True
        return bool(required & set(self.covered_obligation_ids))

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifact_id": self.artifact_id,
            "producer_route": self.producer_route,
            "command": self.command,
            "result_path": self.result_path,
            "result_status": self.result_status,
            "exit_code": self.exit_code,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "artifact_fingerprints": dict(self.artifact_fingerprints),
            "covered_obligation_ids": list(self.covered_obligation_ids),
            "assertion_scope": self.assertion_scope,
            "current": self.current,
            "route_evidence_current": self.route_evidence_current,
            "progress_only": self.progress_only,
            "stale_reasons": list(self.stale_reasons),
            "route_gap_codes": list(self.route_gap_codes),
            "metadata": to_jsonable(dict(self.metadata)),
        }


def coerce_proof_artifact_ref(value: ProofArtifactRef | Mapping[str, Any] | None) -> ProofArtifactRef | None:
    """Return a `ProofArtifactRef` from an existing instance or mapping."""

    if value is None or isinstance(value, ProofArtifactRef):
        return value
    return ProofArtifactRef(**dict(value))


def proof_artifact_gap_codes(
    artifact: ProofArtifactRef | None,
    *,
    declared_status: str = "",
    required_obligation_ids: Sequence[str] = (),
    require_result_path: bool = False,
    require_fingerprints: bool = False,
    require_external_scope: bool = False,
) -> tuple[tuple[str, str], ...]:
    """Return normalized gap codes explaining why a proof artifact is not usable."""

    if artifact is None:
        return (("missing_proof_artifact", "evidence has no proof artifact reference"),)

    gaps: list[tuple[str, str]] = []
    if declared_status and artifact.result_status != declared_status:
        gaps.append(
            (
                "proof_artifact_status_mismatch",
                f"declared status {declared_status} does not match proof artifact status {artifact.result_status}",
            )
        )
    if artifact.result_status not in PASSING_PROOF_ARTIFACT_STATUSES:
        gaps.append(("proof_artifact_not_passing", f"proof artifact status is {artifact.result_status}"))
    if artifact.exit_code not in (None, 0):
        gaps.append(("proof_artifact_nonzero_exit", f"proof artifact exit code is {artifact.exit_code}"))
    if not artifact.current or artifact.stale_reasons or not artifact.route_evidence_current:
        gaps.append(("stale_proof_artifact", "proof artifact or its route evidence is stale"))
    if artifact.progress_only:
        gaps.append(("progress_only_proof_artifact", "proof artifact is progress-only"))
    if artifact.route_gap_codes:
        gaps.append(("proof_artifact_route_gap_visible", "proof artifact route still has unresolved gaps"))
    if require_result_path and not artifact.result_path:
        gaps.append(("proof_artifact_missing_result_path", "proof artifact has no result path"))
    if require_fingerprints and not artifact.artifact_fingerprints:
        gaps.append(("proof_artifact_missing_fingerprint", "proof artifact has no artifact fingerprints"))
    if required_obligation_ids and not artifact.covers_any(required_obligation_ids):
        gaps.append(("proof_artifact_missing_obligation", "proof artifact does not cover required obligations"))
    if require_external_scope and not artifact.has_external_scope():
        gaps.append(("proof_artifact_internal_path_only", "proof artifact does not exercise the external contract"))
    return tuple(gaps)
