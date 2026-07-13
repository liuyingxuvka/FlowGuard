"""Review helpers for reusing previous test results as current evidence."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from .export import to_jsonable


__test__ = False


def _as_tuple(values: Sequence[str] | None) -> tuple[str, ...]:
    if values is None:
        return ()
    return tuple(str(value) for value in values)


def _as_str_map(values: Mapping[str, Any] | None) -> dict[str, str]:
    if not values:
        return {}
    return {str(key): str(value) for key, value in values.items()}


@dataclass(frozen=True)
class TestResultReuseTicket:
    """Proof that a previous test result still applies to current evidence."""

    evidence_id: str
    previous_evidence_id: str = ""
    reason: str = ""
    same_output_proof_id: str = ""
    command_fingerprint: str = ""
    test_source_fingerprint: str = ""
    tested_artifact_fingerprint: str = ""
    dependency_fingerprints: Mapping[str, str] = field(default_factory=dict)
    environment_fingerprint: str = ""
    result_fingerprint: str = ""
    covered_obligation_ids: tuple[str, ...] = ()
    ticket_current: bool = True
    command_current: bool = True
    test_source_current: bool = True
    tested_artifacts_current: bool = True
    dependencies_current: bool = True
    environment_current: bool = True
    previous_result_current: bool = True
    result_fingerprint_matches: bool = True
    coverage_scope_current: bool = True
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "evidence_id", str(self.evidence_id))
        object.__setattr__(self, "previous_evidence_id", str(self.previous_evidence_id))
        object.__setattr__(self, "reason", str(self.reason))
        object.__setattr__(self, "same_output_proof_id", str(self.same_output_proof_id))
        object.__setattr__(self, "command_fingerprint", str(self.command_fingerprint))
        object.__setattr__(self, "test_source_fingerprint", str(self.test_source_fingerprint))
        object.__setattr__(self, "tested_artifact_fingerprint", str(self.tested_artifact_fingerprint))
        object.__setattr__(self, "dependency_fingerprints", _as_str_map(self.dependency_fingerprints))
        object.__setattr__(self, "environment_fingerprint", str(self.environment_fingerprint))
        object.__setattr__(self, "result_fingerprint", str(self.result_fingerprint))
        object.__setattr__(self, "covered_obligation_ids", _as_tuple(self.covered_obligation_ids))
        object.__setattr__(self, "metadata", dict(self.metadata))

    def has_current_reuse_proof(self) -> bool:
        return not test_result_reuse_gap_codes(self)

    def covers_all(self, obligation_ids: Sequence[str]) -> bool:
        required = {str(value) for value in obligation_ids if str(value)}
        if not required:
            return True
        return required.issubset(set(self.covered_obligation_ids))

    def to_dict(self) -> dict[str, Any]:
        return {
            "evidence_id": self.evidence_id,
            "previous_evidence_id": self.previous_evidence_id,
            "reason": self.reason,
            "same_output_proof_id": self.same_output_proof_id,
            "command_fingerprint": self.command_fingerprint,
            "test_source_fingerprint": self.test_source_fingerprint,
            "tested_artifact_fingerprint": self.tested_artifact_fingerprint,
            "dependency_fingerprints": dict(self.dependency_fingerprints),
            "environment_fingerprint": self.environment_fingerprint,
            "result_fingerprint": self.result_fingerprint,
            "covered_obligation_ids": list(self.covered_obligation_ids),
            "ticket_current": self.ticket_current,
            "command_current": self.command_current,
            "test_source_current": self.test_source_current,
            "tested_artifacts_current": self.tested_artifacts_current,
            "dependencies_current": self.dependencies_current,
            "environment_current": self.environment_current,
            "previous_result_current": self.previous_result_current,
            "result_fingerprint_matches": self.result_fingerprint_matches,
            "coverage_scope_current": self.coverage_scope_current,
            "metadata": to_jsonable(dict(self.metadata)),
        }


TestResultReuseTicket.__test__ = False


def coerce_test_result_reuse_ticket(
    value: TestResultReuseTicket | Mapping[str, Any] | None,
) -> TestResultReuseTicket | None:
    """Return a `TestResultReuseTicket` from an existing instance or mapping."""

    if value is None or isinstance(value, TestResultReuseTicket):
        return value
    return TestResultReuseTicket(**dict(value))


def test_result_reuse_gap_codes(
    ticket: TestResultReuseTicket | None,
    *,
    expected_evidence_id: str = "",
    required_obligation_ids: Sequence[str] = (),
) -> tuple[tuple[str, str], ...]:
    """Return normalized gap codes for an unusable test-result reuse ticket."""

    if ticket is None:
        return (("missing_test_reuse_ticket", "reused test evidence has no reuse ticket"),)

    gaps: list[tuple[str, str]] = []
    if expected_evidence_id and ticket.evidence_id != expected_evidence_id:
        gaps.append(
            (
                "test_reuse_evidence_mismatch",
                f"reuse ticket evidence id {ticket.evidence_id} does not match {expected_evidence_id}",
            )
        )
    if not ticket.reason:
        gaps.append(("test_reuse_missing_reason", "reuse ticket does not explain why the old result is reusable"))
    if not ticket.previous_evidence_id:
        gaps.append(("test_reuse_missing_previous_evidence", "reuse ticket does not name previous evidence"))
    if not ticket.result_fingerprint:
        gaps.append(("test_reuse_missing_result_fingerprint", "reuse ticket has no result fingerprint"))
    if not ticket.command_fingerprint:
        gaps.append(("test_reuse_missing_command_fingerprint", "reuse ticket has no command fingerprint"))
    if not ticket.test_source_fingerprint:
        gaps.append(("test_reuse_missing_source_fingerprint", "reuse ticket has no test-source fingerprint"))
    if not ticket.tested_artifact_fingerprint:
        gaps.append(("test_reuse_missing_tested_artifact_fingerprint", "reuse ticket has no tested-artifact fingerprint"))
    if not ticket.dependency_fingerprints:
        gaps.append(("test_reuse_missing_dependency_fingerprints", "reuse ticket has no dependency fingerprints"))
    if not ticket.environment_fingerprint:
        gaps.append(("test_reuse_missing_environment_fingerprint", "reuse ticket has no environment fingerprint"))
    if not ticket.ticket_current:
        gaps.append(("test_reuse_ticket_not_current", "reuse ticket is not marked current"))
    if not ticket.command_current:
        gaps.append(("test_reuse_command_stale", "test command fingerprint is stale"))
    if not ticket.test_source_current:
        gaps.append(("test_reuse_source_stale", "test source fingerprint is stale"))
    if not ticket.tested_artifacts_current:
        gaps.append(("test_reuse_tested_artifact_stale", "tested artifact fingerprint is stale"))
    if not ticket.dependencies_current:
        gaps.append(("test_reuse_dependencies_stale", "dependency fingerprints are stale"))
    if not ticket.environment_current:
        gaps.append(("test_reuse_environment_stale", "environment fingerprint is stale"))
    if not ticket.previous_result_current:
        gaps.append(("test_reuse_previous_result_stale", "previous test result is stale"))
    if not ticket.result_fingerprint_matches:
        gaps.append(("test_reuse_result_fingerprint_mismatch", "result fingerprint no longer matches"))
    if not ticket.coverage_scope_current:
        gaps.append(("test_reuse_coverage_scope_stale", "covered obligation scope is stale"))
    if required_obligation_ids and not ticket.covers_all(required_obligation_ids):
        gaps.append(("test_reuse_missing_obligation", "reuse ticket does not cover required obligations"))
    return tuple(gaps)
