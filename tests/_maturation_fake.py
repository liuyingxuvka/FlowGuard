"""Plain maturation verdicts for admission tests (no receipt store)."""

from __future__ import annotations

from dataclasses import asdict, dataclass

from flowguard._hashing import canonical_fingerprint

MODEL_MATURATION_DECISION_CLOSED_FOR_TASK = "model_maturation_closed_for_task"
MODEL_MATURATION_DECISION_PROGRESS_STALLED = "model_maturation_progress_stalled"


@dataclass(frozen=True)
class MaturationVerdict:
    model_id: str
    task_id: str
    evidence_id: str
    current: bool
    closed: bool
    decision: str
    candidate_model_fingerprint: str
    coverage_universe_fingerprint: str
    input_fingerprint: str
    evidence_fingerprint: str
    open_gap_fingerprints: tuple[str, ...]

    def supports_full_confidence(self) -> bool:
        return self.current and self.closed and not self.open_gap_fingerprints

    def to_dict(self) -> dict:
        return asdict(self)


def verified_maturation(
    *,
    closed: bool = True,
    task_id: str = "task:test",
    evidence_id: str = "maturation:test",
    model_id: str = "model:test",
    gap: str = "gap:test",
) -> MaturationVerdict:
    return MaturationVerdict(
        model_id=model_id,
        task_id=task_id,
        evidence_id=evidence_id,
        current=True,
        closed=closed,
        decision=MODEL_MATURATION_DECISION_CLOSED_FOR_TASK if closed else MODEL_MATURATION_DECISION_PROGRESS_STALLED,
        candidate_model_fingerprint=canonical_fingerprint({"candidate": model_id, "task_id": task_id}),
        coverage_universe_fingerprint="sha256:coverage",
        input_fingerprint="sha256:input",
        evidence_fingerprint="sha256:evidence",
        open_gap_fingerprints=() if closed else (gap,),
    )
