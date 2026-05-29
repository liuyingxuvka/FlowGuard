"""Lightweight evidence field structures for gradual FlowGuard contraction."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from .export import to_jsonable


EVIDENCE_GATE_STATUS_PASSED = "passed"
EVIDENCE_GATE_STATUS_FAILED = "failed"
EVIDENCE_GATE_STATUS_SKIPPED = "skipped"
EVIDENCE_GATE_STATUS_STALE = "stale"
EVIDENCE_GATE_STATUS_NOT_RUN = "not_run"
EVIDENCE_GATE_STATUS_RUNNING = "running"
EVIDENCE_GATE_STATUS_PROGRESS_ONLY = "progress_only"
EVIDENCE_GATE_STATUS_ERROR = "error"

PASSING_EVIDENCE_GATE_STATUSES = (EVIDENCE_GATE_STATUS_PASSED,)
NON_PASSING_EVIDENCE_GATE_STATUSES = (
    EVIDENCE_GATE_STATUS_FAILED,
    EVIDENCE_GATE_STATUS_SKIPPED,
    EVIDENCE_GATE_STATUS_STALE,
    EVIDENCE_GATE_STATUS_NOT_RUN,
    EVIDENCE_GATE_STATUS_RUNNING,
    EVIDENCE_GATE_STATUS_PROGRESS_ONLY,
    EVIDENCE_GATE_STATUS_ERROR,
)


def _tuple(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,) if value else ()
    return tuple(str(item) for item in value if str(item))


@dataclass(frozen=True)
class EvidenceGate:
    gate_id: str
    gate_kind: str
    required: bool = True
    result_status: str = EVIDENCE_GATE_STATUS_NOT_RUN
    current: bool = False
    confidence: str = ""
    scoped_reasons: tuple[str, ...] = ()
    proof_evidence_ids: tuple[str, ...] = ()
    next_actions: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict, compare=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "gate_id", str(self.gate_id))
        object.__setattr__(self, "gate_kind", str(self.gate_kind))
        object.__setattr__(self, "result_status", str(self.result_status or EVIDENCE_GATE_STATUS_NOT_RUN))
        object.__setattr__(self, "confidence", str(self.confidence))
        object.__setattr__(self, "scoped_reasons", _tuple(self.scoped_reasons))
        object.__setattr__(self, "proof_evidence_ids", _tuple(self.proof_evidence_ids))
        object.__setattr__(self, "next_actions", _tuple(self.next_actions))
        object.__setattr__(self, "metadata", dict(self.metadata))

    @property
    def passing(self) -> bool:
        if not self.required:
            return True
        return self.current and self.result_status in PASSING_EVIDENCE_GATE_STATUSES

    @property
    def visible_gap(self) -> bool:
        return self.required and not self.passing

    def to_dict(self) -> dict[str, Any]:
        return {
            "gate_id": self.gate_id,
            "gate_kind": self.gate_kind,
            "required": self.required,
            "result_status": self.result_status,
            "current": self.current,
            "confidence": self.confidence,
            "scoped_reasons": list(self.scoped_reasons),
            "proof_evidence_ids": list(self.proof_evidence_ids),
            "next_actions": list(self.next_actions),
            "passing": self.passing,
            "visible_gap": self.visible_gap,
            "metadata": to_jsonable(dict(self.metadata)),
        }


@dataclass(frozen=True)
class CommandEvidenceDetail:
    command: str
    result_status: str = EVIDENCE_GATE_STATUS_NOT_RUN
    current: bool = False
    proof_artifact: str = ""
    result_path: str = ""

    def to_gate(self, gate_id: str = "command") -> EvidenceGate:
        return EvidenceGate(
            gate_id=gate_id,
            gate_kind="command",
            result_status=self.result_status,
            current=self.current,
            proof_evidence_ids=(self.proof_artifact or self.result_path,),
            metadata={"command": self.command},
        )


@dataclass(frozen=True)
class BackgroundEvidenceDetail:
    background: bool = False
    has_exit_artifact: bool = False
    has_result_artifact: bool = False
    progress_only: bool = False

    def to_gate(self, gate_id: str = "background") -> EvidenceGate:
        status = EVIDENCE_GATE_STATUS_PROGRESS_ONLY if self.progress_only else EVIDENCE_GATE_STATUS_PASSED
        current = (not self.background) or (self.has_exit_artifact and self.has_result_artifact and not self.progress_only)
        return EvidenceGate(
            gate_id=gate_id,
            gate_kind="background",
            result_status=status,
            current=current,
            metadata={
                "background": self.background,
                "has_exit_artifact": self.has_exit_artifact,
                "has_result_artifact": self.has_result_artifact,
                "progress_only": self.progress_only,
            },
        )


@dataclass(frozen=True)
class MeshSplitEvidenceDetail:
    gate_id: str
    current: bool = False
    confidence: str = ""
    suggested_child_ids: tuple[str, ...] = ()
    scoped_reasons: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "suggested_child_ids", _tuple(self.suggested_child_ids))
        object.__setattr__(self, "scoped_reasons", _tuple(self.scoped_reasons))

    def to_gate(self) -> EvidenceGate:
        return EvidenceGate(
            gate_id=self.gate_id,
            gate_kind="mesh_split",
            result_status=EVIDENCE_GATE_STATUS_PASSED if self.current else EVIDENCE_GATE_STATUS_NOT_RUN,
            current=self.current,
            confidence=self.confidence,
            scoped_reasons=self.scoped_reasons,
            metadata={"suggested_child_ids": list(self.suggested_child_ids)},
        )


def summarize_evidence_gates(gates: tuple[EvidenceGate, ...]) -> dict[str, Any]:
    visible_gaps = tuple(gate for gate in gates if gate.visible_gap)
    return {
        "ok": not visible_gaps,
        "total": len(gates),
        "passing": sum(1 for gate in gates if gate.passing),
        "visible_gap_ids": [gate.gate_id for gate in visible_gaps],
        "non_passing_statuses": sorted({gate.result_status for gate in visible_gaps}),
    }


def evidence_gates_from_process_like(evidence: Any) -> tuple[EvidenceGate, ...]:
    command = CommandEvidenceDetail(
        command=str(getattr(evidence, "command", "")),
        result_status=str(getattr(evidence, "status", EVIDENCE_GATE_STATUS_NOT_RUN)),
        current=not bool(getattr(evidence, "stale_reasons", ())),
        proof_artifact=str(getattr(evidence, "proof_artifact", "")),
        result_path=str(getattr(evidence, "result_path", "")),
    ).to_gate("process_command")
    background = BackgroundEvidenceDetail(
        background=bool(getattr(evidence, "background", False)),
        has_exit_artifact=bool(getattr(evidence, "has_exit_artifact", False)),
        has_result_artifact=bool(getattr(evidence, "has_result_artifact", False)),
        progress_only=bool(getattr(evidence, "progress_only", False)),
    ).to_gate("process_background")
    mesh = MeshSplitEvidenceDetail(
        gate_id=str(getattr(evidence, "auto_split_gate_id", "")) or "process_mesh_split",
        current=bool(getattr(evidence, "auto_split_current", False)),
        confidence=str(getattr(evidence, "auto_split_confidence", "")),
        suggested_child_ids=getattr(evidence, "auto_split_suggested_child_ids", ()),
        scoped_reasons=getattr(evidence, "auto_split_scoped_reasons", ()),
    ).to_gate()
    return (command, background, mesh)


__all__ = [
    "BackgroundEvidenceDetail",
    "CommandEvidenceDetail",
    "EVIDENCE_GATE_STATUS_ERROR",
    "EVIDENCE_GATE_STATUS_FAILED",
    "EVIDENCE_GATE_STATUS_NOT_RUN",
    "EVIDENCE_GATE_STATUS_PASSED",
    "EVIDENCE_GATE_STATUS_PROGRESS_ONLY",
    "EVIDENCE_GATE_STATUS_RUNNING",
    "EVIDENCE_GATE_STATUS_SKIPPED",
    "EVIDENCE_GATE_STATUS_STALE",
    "EvidenceGate",
    "MeshSplitEvidenceDetail",
    "NON_PASSING_EVIDENCE_GATE_STATUSES",
    "PASSING_EVIDENCE_GATE_STATUSES",
    "evidence_gates_from_process_like",
    "summarize_evidence_gates",
]
