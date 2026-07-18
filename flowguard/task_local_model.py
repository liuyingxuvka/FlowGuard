"""Immutable task-local prediction and candidate model revision records."""

from __future__ import annotations

from dataclasses import dataclass, replace
import re
from typing import Any, Iterable

from .export import trace_to_dict
from .model_purpose import canonical_fingerprint
from .trace import Trace


TASK_MODEL_SCHEMA = "flowguard.task_model_version.v1"
TASK_PREDICTION_SCHEMA = "flowguard.task_prediction_snapshot.v1"
TASK_REPLAY_EVIDENCE_SCHEMA = "flowguard.task_replay_evidence.v1"
TASK_REVISION_SCHEMA = "flowguard.task_model_revision.v1"
REVISION_PROPOSED = "proposed"
REVISION_ACCEPTED = "accepted"
REVISION_REJECTED = "rejected"
REVISION_ROLLED_BACK = "rolled_back"
_SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


class TaskModelRevisionError(ValueError):
    """Raised when a task-local prediction or revision violates its contract."""


def _required_text(value: Any, field_name: str) -> str:
    result = " ".join(str(value or "").split())
    if not result:
        raise TaskModelRevisionError(f"{field_name} must be non-empty")
    return result


def _required_fingerprint(value: Any, field_name: str) -> str:
    result = str(value or "").strip()
    if not _SHA256_RE.fullmatch(result):
        raise TaskModelRevisionError(f"{field_name} must be a sha256 fingerprint")
    return result


def _unique_ids(values: Iterable[Any], field_name: str) -> tuple[str, ...]:
    result = tuple(_required_text(value, field_name) for value in values)
    if len(result) != len(set(result)):
        raise TaskModelRevisionError(f"{field_name} must not contain duplicates")
    return result


@dataclass(frozen=True)
class TaskModelVersion:
    """One immutable task-model version; never a Guard-core version."""

    version_id: str
    model_fingerprint: str
    artifact_ref: str = ""
    schema: str = TASK_MODEL_SCHEMA

    def __post_init__(self) -> None:
        object.__setattr__(self, "version_id", _required_text(self.version_id, "version_id"))
        object.__setattr__(
            self,
            "model_fingerprint",
            _required_fingerprint(self.model_fingerprint, "model_fingerprint"),
        )
        object.__setattr__(self, "artifact_ref", str(self.artifact_ref or "").strip())
        if self.schema != TASK_MODEL_SCHEMA:
            raise TaskModelRevisionError(f"schema must be {TASK_MODEL_SCHEMA!r}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "version_id": self.version_id,
            "model_fingerprint": self.model_fingerprint,
            "artifact_ref": self.artifact_ref,
        }


@dataclass(frozen=True)
class TaskPredictionSnapshot:
    """A prediction frozen before the named observation boundary is crossed."""

    prediction_id: str
    task_id: str
    model_id: str
    scenario_id: str
    model_version: TaskModelVersion
    expected_trace: Trace
    falsifier: str
    observation_boundary_id: str
    schema: str = TASK_PREDICTION_SCHEMA
    trace_fingerprint: str = ""
    prediction_fingerprint: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "prediction_id",
            _required_text(self.prediction_id, "prediction_id"),
        )
        object.__setattr__(self, "task_id", _required_text(self.task_id, "task_id"))
        object.__setattr__(self, "model_id", _required_text(self.model_id, "model_id"))
        object.__setattr__(
            self,
            "scenario_id",
            _required_text(self.scenario_id, "scenario_id"),
        )
        object.__setattr__(self, "falsifier", _required_text(self.falsifier, "falsifier"))
        object.__setattr__(
            self,
            "observation_boundary_id",
            _required_text(self.observation_boundary_id, "observation_boundary_id"),
        )
        if not isinstance(self.model_version, TaskModelVersion):
            raise TaskModelRevisionError("model_version must be TaskModelVersion")
        if not isinstance(self.expected_trace, Trace):
            raise TaskModelRevisionError("expected_trace must be Trace")
        if self.schema != TASK_PREDICTION_SCHEMA:
            raise TaskModelRevisionError(f"schema must be {TASK_PREDICTION_SCHEMA!r}")

        trace_fingerprint = canonical_fingerprint(
            {"expected_trace": trace_to_dict(self.expected_trace)}
        )
        object.__setattr__(self, "trace_fingerprint", trace_fingerprint)
        object.__setattr__(
            self,
            "prediction_fingerprint",
            canonical_fingerprint(self.prediction_payload()),
        )

    def prediction_payload(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "prediction_id": self.prediction_id,
            "task_id": self.task_id,
            "model_id": self.model_id,
            "scenario_id": self.scenario_id,
            "model_version": self.model_version.to_dict(),
            "trace_fingerprint": self.trace_fingerprint,
            "falsifier": self.falsifier,
            "observation_boundary_id": self.observation_boundary_id,
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            **self.prediction_payload(),
            "prediction_fingerprint": self.prediction_fingerprint,
            "expected_trace": trace_to_dict(self.expected_trace),
        }


@dataclass(frozen=True)
class TaskReplayEvidence:
    """One real conformance report bound to a candidate task-model version."""

    replay_id: str
    task_id: str
    model_id: str
    prediction_id: str
    prediction_fingerprint: str
    model_fingerprint: str
    report_fingerprint: str
    observation_boundary_id: str
    status: str
    schema: str = TASK_REPLAY_EVIDENCE_SCHEMA

    def __post_init__(self) -> None:
        for field_name in (
            "replay_id",
            "task_id",
            "model_id",
            "prediction_id",
            "observation_boundary_id",
        ):
            object.__setattr__(
                self,
                field_name,
                _required_text(getattr(self, field_name), field_name),
            )
        for field_name in (
            "prediction_fingerprint",
            "model_fingerprint",
            "report_fingerprint",
        ):
            object.__setattr__(
                self,
                field_name,
                _required_fingerprint(getattr(self, field_name), field_name),
            )
        if self.status not in {"pass", "fail"}:
            raise TaskModelRevisionError("status must be 'pass' or 'fail'")
        if self.schema != TASK_REPLAY_EVIDENCE_SCHEMA:
            raise TaskModelRevisionError(
                f"schema must be {TASK_REPLAY_EVIDENCE_SCHEMA!r}"
            )

    @classmethod
    def from_conformance_report(
        cls,
        replay_id: str,
        prediction: TaskPredictionSnapshot,
        report: Any,
    ) -> "TaskReplayEvidence":
        """Bind a real report without importing ConformanceReport here."""

        report_payload = report.to_dict()
        bindings = {
            "prediction_id": prediction.prediction_id,
            "prediction_fingerprint": prediction.prediction_fingerprint,
            "model_fingerprint": prediction.model_version.model_fingerprint,
            "observation_boundary_id": prediction.observation_boundary_id,
        }
        for field_name, expected in bindings.items():
            if getattr(report, field_name, None) != expected:
                raise TaskModelRevisionError(
                    f"conformance report {field_name} is not bound to the prediction"
                )
        return cls(
            replay_id=replay_id,
            task_id=prediction.task_id,
            model_id=prediction.model_id,
            prediction_id=prediction.prediction_id,
            prediction_fingerprint=prediction.prediction_fingerprint,
            model_fingerprint=prediction.model_version.model_fingerprint,
            report_fingerprint=canonical_fingerprint(report_payload),
            observation_boundary_id=prediction.observation_boundary_id,
            status="pass" if bool(report.ok) else "fail",
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "replay_id": self.replay_id,
            "task_id": self.task_id,
            "model_id": self.model_id,
            "prediction_id": self.prediction_id,
            "prediction_fingerprint": self.prediction_fingerprint,
            "model_fingerprint": self.model_fingerprint,
            "report_fingerprint": self.report_fingerprint,
            "observation_boundary_id": self.observation_boundary_id,
            "status": self.status,
        }


@dataclass(frozen=True)
class TaskModelRevision:
    """Candidate-only task model transition with explicit acceptance evidence."""

    revision_id: str
    task_id: str
    model_id: str
    base_model: TaskModelVersion
    candidate_model: TaskModelVersion
    prediction_id: str
    mismatch_summary: str
    changed_model_elements: tuple[str, ...]
    required_replay_ids: tuple[str, ...]
    status: str = REVISION_PROPOSED
    completed_replay_ids: tuple[str, ...] = ()
    decision_reason: str = ""
    schema: str = TASK_REVISION_SCHEMA

    def __post_init__(self) -> None:
        object.__setattr__(self, "revision_id", _required_text(self.revision_id, "revision_id"))
        object.__setattr__(self, "task_id", _required_text(self.task_id, "task_id"))
        object.__setattr__(self, "model_id", _required_text(self.model_id, "model_id"))
        object.__setattr__(
            self,
            "prediction_id",
            _required_text(self.prediction_id, "prediction_id"),
        )
        object.__setattr__(
            self,
            "mismatch_summary",
            _required_text(self.mismatch_summary, "mismatch_summary"),
        )
        object.__setattr__(
            self,
            "changed_model_elements",
            _unique_ids(self.changed_model_elements, "changed_model_elements"),
        )
        object.__setattr__(
            self,
            "required_replay_ids",
            _unique_ids(self.required_replay_ids, "required_replay_ids"),
        )
        object.__setattr__(
            self,
            "completed_replay_ids",
            _unique_ids(self.completed_replay_ids, "completed_replay_ids"),
        )
        object.__setattr__(self, "decision_reason", str(self.decision_reason or "").strip())
        if not isinstance(self.base_model, TaskModelVersion):
            raise TaskModelRevisionError("base_model must be TaskModelVersion")
        if not isinstance(self.candidate_model, TaskModelVersion):
            raise TaskModelRevisionError("candidate_model must be TaskModelVersion")
        if self.base_model.version_id == self.candidate_model.version_id:
            raise TaskModelRevisionError("candidate model version must differ from base")
        if not self.changed_model_elements:
            raise TaskModelRevisionError("changed_model_elements must be non-empty")
        if not self.required_replay_ids:
            raise TaskModelRevisionError("required_replay_ids must be non-empty")
        if self.status not in {
            REVISION_PROPOSED,
            REVISION_ACCEPTED,
            REVISION_REJECTED,
            REVISION_ROLLED_BACK,
        }:
            raise TaskModelRevisionError(f"unsupported revision status: {self.status!r}")
        if self.schema != TASK_REVISION_SCHEMA:
            raise TaskModelRevisionError(f"schema must be {TASK_REVISION_SCHEMA!r}")
        if self.status == REVISION_ACCEPTED:
            missing = set(self.required_replay_ids) - set(self.completed_replay_ids)
            if missing:
                raise TaskModelRevisionError(
                    f"accepted revision is missing required replays: {sorted(missing)}"
                )

    @property
    def active_model(self) -> TaskModelVersion:
        if self.status == REVISION_ACCEPTED:
            return self.candidate_model
        return self.base_model

    def accept(
        self,
        replay_evidence: Iterable[TaskReplayEvidence],
        *,
        reason: str = "all required task-local replays passed",
    ) -> "TaskModelRevision":
        if self.status != REVISION_PROPOSED:
            raise TaskModelRevisionError("only a proposed revision can be accepted")
        evidence = tuple(replay_evidence)
        if any(not isinstance(item, TaskReplayEvidence) for item in evidence):
            raise TaskModelRevisionError(
                "acceptance requires TaskReplayEvidence from real conformance reports"
            )
        replay_ids = tuple(item.replay_id for item in evidence)
        if len(replay_ids) != len(set(replay_ids)):
            raise TaskModelRevisionError("replay evidence must not contain duplicates")
        missing = set(self.required_replay_ids) - set(replay_ids)
        unexpected = set(replay_ids) - set(self.required_replay_ids)
        if missing:
            raise TaskModelRevisionError(
                f"cannot accept; required replays did not pass: {sorted(missing)}"
            )
        if unexpected:
            raise TaskModelRevisionError(
                f"cannot accept unrelated replay evidence: {sorted(unexpected)}"
            )
        for item in evidence:
            if item.status != "pass":
                raise TaskModelRevisionError(
                    f"cannot accept; replay did not pass: {item.replay_id}"
                )
            if item.task_id != self.task_id or item.model_id != self.model_id:
                raise TaskModelRevisionError(
                    f"cannot accept replay from another task model: {item.replay_id}"
                )
            if item.model_fingerprint != self.candidate_model.model_fingerprint:
                raise TaskModelRevisionError(
                    f"cannot accept replay not bound to candidate model: {item.replay_id}"
                )
        completed = tuple(
            item for item in self.required_replay_ids if item in set(replay_ids)
        )
        return replace(
            self,
            status=REVISION_ACCEPTED,
            completed_replay_ids=completed,
            decision_reason=_required_text(reason, "reason"),
        )

    def reject(self, reason: str) -> "TaskModelRevision":
        if self.status != REVISION_PROPOSED:
            raise TaskModelRevisionError("only a proposed revision can be rejected")
        return replace(
            self,
            status=REVISION_REJECTED,
            decision_reason=_required_text(reason, "reason"),
        )

    def rollback(self, reason: str) -> "TaskModelRevision":
        if self.status != REVISION_ACCEPTED:
            raise TaskModelRevisionError("only an accepted revision can be rolled back")
        return replace(
            self,
            status=REVISION_ROLLED_BACK,
            decision_reason=_required_text(reason, "reason"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "revision_id": self.revision_id,
            "task_id": self.task_id,
            "model_id": self.model_id,
            "base_model": self.base_model.to_dict(),
            "candidate_model": self.candidate_model.to_dict(),
            "prediction_id": self.prediction_id,
            "mismatch_summary": self.mismatch_summary,
            "changed_model_elements": list(self.changed_model_elements),
            "required_replay_ids": list(self.required_replay_ids),
            "status": self.status,
            "completed_replay_ids": list(self.completed_replay_ids),
            "decision_reason": self.decision_reason,
            "active_model": self.active_model.to_dict(),
        }


__all__ = [
    "REVISION_ACCEPTED",
    "REVISION_PROPOSED",
    "REVISION_REJECTED",
    "REVISION_ROLLED_BACK",
    "TASK_MODEL_SCHEMA",
    "TASK_PREDICTION_SCHEMA",
    "TASK_REPLAY_EVIDENCE_SCHEMA",
    "TASK_REVISION_SCHEMA",
    "TaskModelRevision",
    "TaskModelRevisionError",
    "TaskModelVersion",
    "TaskPredictionSnapshot",
    "TaskReplayEvidence",
]
