"""Model maturation loop review helpers.

This helper turns post-code, post-test, mesh, freshness, or model-miss signals
into explicit model-upgrade actions before a broad FlowGuard claim is made.
It does not replace the owning satellite routes; it records when their evidence
means the model itself is too coarse, stale, or only supports scoped confidence.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
import hashlib
import json
from typing import Any, Mapping, Sequence

from .export import to_jsonable
from .maintenance_obligation import (
    MaintenanceObligation,
    coerce_maintenance_obligation,
    obligations_from_maturation_findings,
)
from .proof_artifact import ProofArtifactRef, coerce_proof_artifact_ref


MODEL_MATURATION_DECISION_CLOSED_FOR_TASK = "model_maturation_closed_for_task"
MODEL_MATURATION_DECISION_PROGRESS_STALLED = "model_maturation_progress_stalled"
MODEL_MATURATION_DECISION_ITERATION_LIMIT = "model_maturation_iteration_limit"
MODEL_MATURATION_DECISION_EXTERNAL_INPUT_REQUIRED = "model_maturation_external_input_required"
MODEL_MATURATION_DECISION_SCOPE_EXCLUDED = "model_maturation_scope_excluded"
MODEL_MATURATION_DECISION_UPGRADE_REQUIRED = "model_maturation_upgrade_required"
MODEL_MATURATION_DECISION_BLOCKED = "model_maturation_blocked"

MODEL_MATURATION_PLAN_SCHEMA_VERSION = "flowguard.model-maturation-plan.v2"
MODEL_MATURATION_INTAKE_SCHEMA_VERSION = "flowguard.model-maturation-intake.v1"
MODEL_MATURATION_RECEIPT_STATUS_PASS = "pass"

MODEL_MATURATION_CONFIDENCE_FULL = "full"
MODEL_MATURATION_CONFIDENCE_SCOPED = "scoped"
MODEL_MATURATION_CONFIDENCE_BLOCKED = "blocked"

MODEL_MATURATION_RESOLUTION_MODEL_EDIT = "model_edit"
MODEL_MATURATION_RESOLUTION_EVIDENCE_ACQUISITION = "evidence_acquisition"
MODEL_MATURATION_RESOLUTION_EXTERNAL_INPUT_REQUIRED = "external_input_required"
MODEL_MATURATION_RESOLUTION_SCOPE_EXCLUDED = "scope_excluded"
MODEL_MATURATION_RESOLUTION_CLASSES = (
    MODEL_MATURATION_RESOLUTION_MODEL_EDIT,
    MODEL_MATURATION_RESOLUTION_EVIDENCE_ACQUISITION,
    MODEL_MATURATION_RESOLUTION_EXTERNAL_INPUT_REQUIRED,
    MODEL_MATURATION_RESOLUTION_SCOPE_EXCLUDED,
)

MATURITY_ACTION_NO_CHANGE = "no_model_change_needed"
MATURITY_ACTION_ADD_STATE_FIELD = "add_state_field"
MATURITY_ACTION_ADD_TRANSITION_CASE = "add_transition_case"
MATURITY_ACTION_ADD_INVARIANT = "add_invariant"
MATURITY_ACTION_ADD_SAME_CLASS_SCENARIO = "add_same_class_scenario"
MATURITY_ACTION_SPLIT_CHILD_MODEL = "split_child_model"
MATURITY_ACTION_REATTACH_PARENT_MODEL = "reattach_parent_model"
MATURITY_ACTION_REFRESH_EVIDENCE = "refresh_evidence"
MATURITY_ACTION_ADD_CODE_BOUNDARY_OBSERVATION = "add_code_boundary_observation"
MATURITY_ACTION_ADD_MODEL_OBLIGATION = "add_model_obligation"
MATURITY_ACTION_DOWNGRADE_CLAIM = "downgrade_claim"

MODEL_MATURATION_SIGNAL_STATE_TOO_COARSE = "state_too_coarse"
MODEL_MATURATION_SIGNAL_INPUT_BRANCH_MISSING = "input_branch_missing"
MODEL_MATURATION_SIGNAL_BOUNDARY_MISSING = "boundary_missing"
MODEL_MATURATION_SIGNAL_INVARIANT_TOO_WEAK = "invariant_too_weak"
MODEL_MATURATION_SIGNAL_SAME_CLASS_MISSING = "same_class_missing"
MODEL_MATURATION_SIGNAL_CHILD_REATTACHMENT_MISSING = "child_reattachment_missing"
MODEL_MATURATION_SIGNAL_CHILD_BOUNDARY_CHANGED = "child_boundary_changed"
MODEL_MATURATION_SIGNAL_DUPLICATE_PRIMARY_EDGE_PATH = "duplicate_primary_edge_path"
MODEL_MATURATION_SIGNAL_OVERSIZED_MODEL = "oversized_model"
MODEL_MATURATION_SIGNAL_MISSING_MODEL_OBLIGATION = "missing_model_obligation"
MODEL_MATURATION_SIGNAL_STALE_EVIDENCE = "stale_evidence"
MODEL_MATURATION_SIGNAL_PROGRESS_ONLY_EVIDENCE = "progress_only_evidence"
MODEL_MATURATION_SIGNAL_CODE_BOUNDARY_MISMATCH = "code_boundary_mismatch"
MODEL_MATURATION_SIGNAL_MISSING_CODE_BOUNDARY_OBSERVATION = "missing_code_boundary_observation"

MODEL_MATURATION_SIGNAL_TYPES = (
    MODEL_MATURATION_SIGNAL_STATE_TOO_COARSE,
    MODEL_MATURATION_SIGNAL_INPUT_BRANCH_MISSING,
    MODEL_MATURATION_SIGNAL_BOUNDARY_MISSING,
    MODEL_MATURATION_SIGNAL_INVARIANT_TOO_WEAK,
    MODEL_MATURATION_SIGNAL_SAME_CLASS_MISSING,
    MODEL_MATURATION_SIGNAL_CHILD_REATTACHMENT_MISSING,
    MODEL_MATURATION_SIGNAL_CHILD_BOUNDARY_CHANGED,
    MODEL_MATURATION_SIGNAL_DUPLICATE_PRIMARY_EDGE_PATH,
    MODEL_MATURATION_SIGNAL_OVERSIZED_MODEL,
    MODEL_MATURATION_SIGNAL_MISSING_MODEL_OBLIGATION,
    MODEL_MATURATION_SIGNAL_STALE_EVIDENCE,
    MODEL_MATURATION_SIGNAL_PROGRESS_ONLY_EVIDENCE,
    MODEL_MATURATION_SIGNAL_CODE_BOUNDARY_MISMATCH,
    MODEL_MATURATION_SIGNAL_MISSING_CODE_BOUNDARY_OBSERVATION,
)

MODEL_MATURATION_TERMINAL_REASONS = (
    MODEL_MATURATION_DECISION_CLOSED_FOR_TASK,
    MODEL_MATURATION_DECISION_BLOCKED,
    MODEL_MATURATION_DECISION_PROGRESS_STALLED,
    MODEL_MATURATION_DECISION_ITERATION_LIMIT,
    MODEL_MATURATION_DECISION_EXTERNAL_INPUT_REQUIRED,
    MODEL_MATURATION_DECISION_SCOPE_EXCLUDED,
)

MODEL_MATURATION_ACTIONS_BY_SIGNAL = {
    MODEL_MATURATION_SIGNAL_STATE_TOO_COARSE: (MATURITY_ACTION_ADD_STATE_FIELD,),
    MODEL_MATURATION_SIGNAL_INPUT_BRANCH_MISSING: (MATURITY_ACTION_ADD_TRANSITION_CASE,),
    MODEL_MATURATION_SIGNAL_BOUNDARY_MISSING: (
        MATURITY_ACTION_ADD_TRANSITION_CASE,
        MATURITY_ACTION_ADD_CODE_BOUNDARY_OBSERVATION,
    ),
    MODEL_MATURATION_SIGNAL_INVARIANT_TOO_WEAK: (MATURITY_ACTION_ADD_INVARIANT,),
    MODEL_MATURATION_SIGNAL_SAME_CLASS_MISSING: (MATURITY_ACTION_ADD_SAME_CLASS_SCENARIO,),
    MODEL_MATURATION_SIGNAL_CHILD_REATTACHMENT_MISSING: (MATURITY_ACTION_REATTACH_PARENT_MODEL,),
    MODEL_MATURATION_SIGNAL_CHILD_BOUNDARY_CHANGED: (MATURITY_ACTION_REATTACH_PARENT_MODEL,),
    MODEL_MATURATION_SIGNAL_DUPLICATE_PRIMARY_EDGE_PATH: (MATURITY_ACTION_SPLIT_CHILD_MODEL,),
    MODEL_MATURATION_SIGNAL_OVERSIZED_MODEL: (MATURITY_ACTION_SPLIT_CHILD_MODEL,),
    MODEL_MATURATION_SIGNAL_MISSING_MODEL_OBLIGATION: (MATURITY_ACTION_ADD_MODEL_OBLIGATION,),
    MODEL_MATURATION_SIGNAL_STALE_EVIDENCE: (MATURITY_ACTION_REFRESH_EVIDENCE,),
    MODEL_MATURATION_SIGNAL_PROGRESS_ONLY_EVIDENCE: (MATURITY_ACTION_REFRESH_EVIDENCE,),
    MODEL_MATURATION_SIGNAL_CODE_BOUNDARY_MISMATCH: (
        MATURITY_ACTION_ADD_CODE_BOUNDARY_OBSERVATION,
        MATURITY_ACTION_ADD_MODEL_OBLIGATION,
    ),
    MODEL_MATURATION_SIGNAL_MISSING_CODE_BOUNDARY_OBSERVATION: (
        MATURITY_ACTION_ADD_CODE_BOUNDARY_OBSERVATION,
    ),
}


def _as_tuple(values: Sequence[str] | None) -> tuple[str, ...]:
    if values is None:
        return ()
    return tuple(str(value) for value in values)


def _unique(values: Sequence[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        text = str(value)
        if text and text not in seen:
            seen.add(text)
            ordered.append(text)
    return tuple(ordered)


def _stable_fingerprint(value: object) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ModelMaturationGapResolutionReceipt:
    """Exact native evidence that one prior gap was resolved."""

    receipt_id: str
    receipt_fingerprint: str
    gap_fingerprint: str
    task_id: str
    candidate_fingerprint: str
    coverage_fingerprint: str
    evidence_fingerprint: str
    owner_route: str
    status: str = ""
    current: bool = False

    def __post_init__(self) -> None:
        for name in (
            "receipt_id",
            "receipt_fingerprint",
            "gap_fingerprint",
            "task_id",
            "candidate_fingerprint",
            "coverage_fingerprint",
            "evidence_fingerprint",
            "owner_route",
            "status",
        ):
            object.__setattr__(self, name, str(getattr(self, name)))
        object.__setattr__(self, "current", bool(self.current))

    def is_verified(
        self,
        *,
        gap_fingerprint: str,
        task_id: str,
        candidate_fingerprint: str,
        coverage_fingerprint: str,
    ) -> bool:
        return bool(
            self.current
            and self.status == MODEL_MATURATION_RECEIPT_STATUS_PASS
            and self.receipt_id
            and self.receipt_fingerprint
            and self.evidence_fingerprint
            and self.owner_route
            and self.gap_fingerprint == gap_fingerprint
            and self.task_id == task_id
            and self.candidate_fingerprint == candidate_fingerprint
            and self.coverage_fingerprint == coverage_fingerprint
        )

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "ModelMaturationGapResolutionReceipt":
        return cls(
            receipt_id=str(value.get("receipt_id", "")),
            receipt_fingerprint=str(value.get("receipt_fingerprint", "")),
            gap_fingerprint=str(value.get("gap_fingerprint", "")),
            task_id=str(value.get("task_id", "")),
            candidate_fingerprint=str(value.get("candidate_fingerprint", "")),
            coverage_fingerprint=str(value.get("coverage_fingerprint", "")),
            evidence_fingerprint=str(value.get("evidence_fingerprint", "")),
            owner_route=str(value.get("owner_route", "")),
            status=str(value.get("status", "")),
            current=bool(value.get("current", False)),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "receipt_id": self.receipt_id,
            "receipt_fingerprint": self.receipt_fingerprint,
            "gap_fingerprint": self.gap_fingerprint,
            "task_id": self.task_id,
            "candidate_fingerprint": self.candidate_fingerprint,
            "coverage_fingerprint": self.coverage_fingerprint,
            "evidence_fingerprint": self.evidence_fingerprint,
            "owner_route": self.owner_route,
            "status": self.status,
            "current": self.current,
        }


@dataclass(frozen=True)
class ModelMaturationSignal:
    """One route signal that may require the model to be upgraded."""

    signal_id: str
    signal_type: str
    source_route: str = ""
    model_id: str = ""
    risk_id: str = ""
    evidence_id: str = ""
    description: str = ""
    in_scope: bool = True
    required: bool = True
    # `resolved` is a caller observation only.  It becomes authoritative only
    # when the exact current receipt bindings below validate.
    resolved: bool = False
    current: bool = False
    suggested_actions: tuple[str, ...] = ()
    coverage_id: str = ""
    resolution_class: str = ""
    prediction: str = ""
    falsifier: str = ""
    evidence_fingerprint: str = ""
    probe_id: str = ""
    receipt_id: str = ""
    receipt_fingerprint: str = ""
    receipt_status: str = ""
    receipt_task_id: str = ""
    receipt_probe_id: str = ""
    receipt_candidate_fingerprint: str = ""
    receipt_coverage_fingerprint: str = ""
    receipt_evidence_fingerprint: str = ""
    receipt_owner_route: str = ""
    required_input: str = ""
    owner_boundary: str = ""
    affected_claim_scope: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "signal_id", str(self.signal_id))
        object.__setattr__(self, "signal_type", str(self.signal_type))
        object.__setattr__(self, "source_route", str(self.source_route))
        object.__setattr__(self, "model_id", str(self.model_id))
        object.__setattr__(self, "risk_id", str(self.risk_id))
        object.__setattr__(self, "evidence_id", str(self.evidence_id))
        object.__setattr__(self, "description", str(self.description))
        object.__setattr__(self, "in_scope", bool(self.in_scope))
        object.__setattr__(self, "required", bool(self.required))
        object.__setattr__(self, "resolved", bool(self.resolved))
        object.__setattr__(self, "current", bool(self.current))
        object.__setattr__(self, "suggested_actions", _as_tuple(self.suggested_actions))
        object.__setattr__(self, "coverage_id", str(self.coverage_id))
        object.__setattr__(self, "resolution_class", str(self.resolution_class))
        object.__setattr__(self, "prediction", str(self.prediction))
        object.__setattr__(self, "falsifier", str(self.falsifier))
        object.__setattr__(self, "evidence_fingerprint", str(self.evidence_fingerprint))
        object.__setattr__(self, "probe_id", str(self.probe_id))
        object.__setattr__(self, "receipt_id", str(self.receipt_id))
        object.__setattr__(self, "receipt_fingerprint", str(self.receipt_fingerprint))
        object.__setattr__(self, "receipt_status", str(self.receipt_status))
        object.__setattr__(self, "receipt_task_id", str(self.receipt_task_id))
        object.__setattr__(self, "receipt_probe_id", str(self.receipt_probe_id))
        object.__setattr__(self, "receipt_candidate_fingerprint", str(self.receipt_candidate_fingerprint))
        object.__setattr__(self, "receipt_coverage_fingerprint", str(self.receipt_coverage_fingerprint))
        object.__setattr__(self, "receipt_evidence_fingerprint", str(self.receipt_evidence_fingerprint))
        object.__setattr__(self, "receipt_owner_route", str(self.receipt_owner_route))
        object.__setattr__(self, "required_input", str(self.required_input))
        object.__setattr__(self, "owner_boundary", str(self.owner_boundary))
        object.__setattr__(self, "affected_claim_scope", str(self.affected_claim_scope))
        object.__setattr__(self, "metadata", dict(self.metadata))

    def is_open(self) -> bool:
        # This convenience predicate is intentionally conservative.  Exact
        # closure still belongs to ``receipt_is_verified`` because only the
        # owning plan can supply the task/candidate/coverage bindings.
        has_receipt_shape = bool(
            self.resolved
            and self.current
            and self.receipt_id
            and self.receipt_fingerprint
            and self.receipt_status == MODEL_MATURATION_RECEIPT_STATUS_PASS
        )
        return self.in_scope and self.required and not has_receipt_shape

    def receipt_is_verified(
        self,
        *,
        task_id: str,
        candidate_fingerprint: str,
        coverage_fingerprint: str,
    ) -> bool:
        """Return whether this signal has exact current terminal evidence.

        The caller's `resolved` bit is intentionally insufficient.  The
        receipt must bind the exact task, probe, candidate, and independently
        frozen coverage universe.
        """

        return self.resolved and self.evidence_receipt_is_verified(
            task_id=task_id,
            candidate_fingerprint=candidate_fingerprint,
            coverage_fingerprint=coverage_fingerprint,
        )

    def evidence_receipt_is_verified(
        self,
        *,
        task_id: str,
        candidate_fingerprint: str,
        coverage_fingerprint: str,
    ) -> bool:
        """Return whether the probe produced exact current native evidence.

        A passing probe receipt may demonstrate discriminating progress while
        the modeled gap remains open.  Closure additionally requires
        ``resolved`` through :meth:`receipt_is_verified`.
        """

        return bool(
            self.current
            and self.prediction.strip()
            and self.falsifier.strip()
            and self.evidence_id.strip()
            and self.evidence_fingerprint.strip()
            and self.probe_id.strip()
            and self.receipt_id.strip()
            and self.receipt_fingerprint.strip()
            and self.receipt_status == MODEL_MATURATION_RECEIPT_STATUS_PASS
            and self.receipt_task_id == task_id
            and self.receipt_probe_id == self.probe_id
            and self.receipt_candidate_fingerprint == candidate_fingerprint
            and self.receipt_coverage_fingerprint == coverage_fingerprint
            and self.receipt_evidence_fingerprint == self.evidence_fingerprint
            and self.receipt_owner_route == self.source_route
        )

    def actions(self) -> tuple[str, ...]:
        if self.suggested_actions:
            return self.suggested_actions
        return MODEL_MATURATION_ACTIONS_BY_SIGNAL.get(
            self.signal_type,
            (MATURITY_ACTION_DOWNGRADE_CLAIM,),
        )

    def resolution(self) -> str:
        value = self.resolution_class
        return value if value in MODEL_MATURATION_RESOLUTION_CLASSES else MODEL_MATURATION_RESOLUTION_MODEL_EDIT

    def gap_fingerprint(self) -> str:
        """Return the stable identity of the unresolved obligation.

        Evidence and receipt fields are deliberately excluded.  They evolve
        while the same gap is investigated and therefore cannot define the
        gap's identity or manufacture apparent progress.
        """

        return _stable_fingerprint(
            {
                "signal_id": self.signal_id,
                "signal_type": self.signal_type,
                "coverage_id": self.coverage_id,
                "description": self.description,
                "resolution_class": self.resolution(),
                "prediction": self.prediction,
                "falsifier": self.falsifier,
                "probe_id": self.probe_id,
            }
        )

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "ModelMaturationSignal":
        allowed = {
            "signal_id", "signal_type", "source_route", "model_id", "risk_id",
            "evidence_id", "description", "in_scope", "required", "resolved",
            "current", "suggested_actions", "coverage_id", "resolution_class",
            "prediction", "falsifier", "evidence_fingerprint", "probe_id",
            "receipt_id", "receipt_fingerprint", "receipt_status", "receipt_task_id",
            "receipt_probe_id", "receipt_candidate_fingerprint",
            "receipt_coverage_fingerprint", "receipt_evidence_fingerprint",
            "receipt_owner_route", "required_input", "owner_boundary",
            "affected_claim_scope", "gap_fingerprint", "metadata",
        }
        unknown = sorted(set(value) - allowed)
        if unknown:
            raise ValueError(f"unknown model maturation signal fields: {unknown}")
        signal = cls(
            signal_id=str(value.get("signal_id", "")),
            signal_type=str(value.get("signal_type", "")),
            source_route=str(value.get("source_route", "")),
            model_id=str(value.get("model_id", "")),
            risk_id=str(value.get("risk_id", "")),
            evidence_id=str(value.get("evidence_id", "")),
            description=str(value.get("description", "")),
            in_scope=bool(value.get("in_scope", True)),
            required=bool(value.get("required", True)),
            resolved=bool(value.get("resolved", False)),
            current=bool(value.get("current", False)),
            suggested_actions=tuple(value.get("suggested_actions", ())),
            coverage_id=str(value.get("coverage_id", "")),
            resolution_class=str(value.get("resolution_class", "")),
            prediction=str(value.get("prediction", "")),
            falsifier=str(value.get("falsifier", "")),
            evidence_fingerprint=str(value.get("evidence_fingerprint", "")),
            probe_id=str(value.get("probe_id", "")),
            receipt_id=str(value.get("receipt_id", "")),
            receipt_fingerprint=str(value.get("receipt_fingerprint", "")),
            receipt_status=str(value.get("receipt_status", "")),
            receipt_task_id=str(value.get("receipt_task_id", "")),
            receipt_probe_id=str(value.get("receipt_probe_id", "")),
            receipt_candidate_fingerprint=str(value.get("receipt_candidate_fingerprint", "")),
            receipt_coverage_fingerprint=str(value.get("receipt_coverage_fingerprint", "")),
            receipt_evidence_fingerprint=str(value.get("receipt_evidence_fingerprint", "")),
            receipt_owner_route=str(value.get("receipt_owner_route", "")),
            required_input=str(value.get("required_input", "")),
            owner_boundary=str(value.get("owner_boundary", "")),
            affected_claim_scope=str(value.get("affected_claim_scope", "")),
            metadata=value.get("metadata", {}) if isinstance(value.get("metadata", {}), Mapping) else {},
        )
        declared_gap = str(value.get("gap_fingerprint", ""))
        if declared_gap and declared_gap != signal.gap_fingerprint():
            raise ValueError("model maturation signal gap fingerprint mismatch")
        return signal

    def to_dict(self) -> dict[str, Any]:
        return {
            "signal_id": self.signal_id,
            "signal_type": self.signal_type,
            "source_route": self.source_route,
            "model_id": self.model_id,
            "risk_id": self.risk_id,
            "evidence_id": self.evidence_id,
            "description": self.description,
            "in_scope": self.in_scope,
            "required": self.required,
            "resolved": self.resolved,
            "current": self.current,
            "suggested_actions": list(self.suggested_actions),
            "coverage_id": self.coverage_id,
            "resolution_class": self.resolution_class or self.resolution(),
            "prediction": self.prediction,
            "falsifier": self.falsifier,
            "evidence_fingerprint": self.evidence_fingerprint,
            "probe_id": self.probe_id,
            "receipt_id": self.receipt_id,
            "receipt_fingerprint": self.receipt_fingerprint,
            "receipt_status": self.receipt_status,
            "receipt_task_id": self.receipt_task_id,
            "receipt_probe_id": self.receipt_probe_id,
            "receipt_candidate_fingerprint": self.receipt_candidate_fingerprint,
            "receipt_coverage_fingerprint": self.receipt_coverage_fingerprint,
            "receipt_evidence_fingerprint": self.receipt_evidence_fingerprint,
            "receipt_owner_route": self.receipt_owner_route,
            "required_input": self.required_input,
            "owner_boundary": self.owner_boundary,
            "affected_claim_scope": self.affected_claim_scope,
            "gap_fingerprint": self.gap_fingerprint(),
            "metadata": to_jsonable(dict(self.metadata)),
        }


@dataclass(frozen=True)
class ModelMaturationCoverageContribution:
    """One native owner's typed contribution to the task coverage denominator."""

    contribution_id: str
    owner_route: str
    task_id: str
    coverage_source_refs: tuple[str, ...] = ()
    coverage_ids: tuple[str, ...] = ()
    required_probe_ids: tuple[str, ...] = ()
    signals: tuple[ModelMaturationSignal, ...] = ()
    evidence_ref: ProofArtifactRef | Mapping[str, Any] | None = None
    subject_fingerprints: Mapping[str, str] = field(default_factory=dict)
    status: str = "pass"
    current: bool = True

    def __post_init__(self) -> None:
        object.__setattr__(self, "contribution_id", str(self.contribution_id))
        object.__setattr__(self, "owner_route", str(self.owner_route))
        object.__setattr__(self, "task_id", str(self.task_id))
        object.__setattr__(self, "coverage_source_refs", _as_tuple(self.coverage_source_refs))
        object.__setattr__(self, "coverage_ids", _as_tuple(self.coverage_ids))
        object.__setattr__(self, "required_probe_ids", _as_tuple(self.required_probe_ids))
        normalized_signals = tuple(
            signal
            if isinstance(signal, ModelMaturationSignal)
            else ModelMaturationSignal.from_dict(signal)
            for signal in self.signals
        )
        object.__setattr__(self, "signals", normalized_signals)
        object.__setattr__(self, "evidence_ref", coerce_proof_artifact_ref(self.evidence_ref))
        object.__setattr__(
            self,
            "subject_fingerprints",
            {str(key): str(value) for key, value in self.subject_fingerprints.items()},
        )
        object.__setattr__(self, "status", str(self.status))
        object.__setattr__(self, "current", bool(self.current))

    def evidence_is_current(self) -> bool:
        proof = self.evidence_ref
        return bool(
            self.current
            and self.status == "pass"
            and proof is not None
            and proof.producer_route == self.owner_route
            and proof.has_current_pass()
            and proof.covers_all(self.coverage_ids)
            and self.subject_fingerprints
            and all(
                proof.artifact_fingerprints.get(key) == value
                for key, value in self.subject_fingerprints.items()
            )
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "contribution_id": self.contribution_id,
            "owner_route": self.owner_route,
            "task_id": self.task_id,
            "coverage_source_refs": list(self.coverage_source_refs),
            "coverage_ids": list(self.coverage_ids),
            "required_probe_ids": list(self.required_probe_ids),
            "signals": [signal.to_dict() for signal in self.signals],
            "evidence_ref": self.evidence_ref.to_dict() if self.evidence_ref else None,
            "subject_fingerprints": dict(self.subject_fingerprints),
            "status": self.status,
            "current": self.current,
        }


@dataclass(frozen=True)
class ModelMaturationIntake:
    """Task-local pre-code or post-code intake compiled into the existing plan."""

    intake_id: str
    plan_id: str
    task_id: str
    task_purpose: str
    model_id: str
    risk_id: str
    base_model_fingerprint: str
    candidate_model_fingerprint: str
    contributions: tuple[ModelMaturationCoverageContribution, ...] = ()
    required_contribution_ids: tuple[str, ...] = ()
    schema_version: str = MODEL_MATURATION_INTAKE_SCHEMA_VERSION
    iteration: int = 0
    max_iterations: int = 8
    prior_gap_fingerprints: tuple[str, ...] = ()
    prior_iteration_fingerprint: str = ""
    prior_candidate_fingerprint: str = ""
    prior_evidence_fingerprint: str = ""
    prior_state_fingerprints: tuple[str, ...] = ()
    resolved_gap_receipts: Mapping[str, ModelMaturationGapResolutionReceipt] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name in (
            "intake_id",
            "plan_id",
            "task_id",
            "task_purpose",
            "model_id",
            "risk_id",
            "base_model_fingerprint",
            "candidate_model_fingerprint",
            "schema_version",
            "prior_iteration_fingerprint",
            "prior_candidate_fingerprint",
            "prior_evidence_fingerprint",
        ):
            object.__setattr__(self, name, str(getattr(self, name)))
        if self.schema_version != MODEL_MATURATION_INTAKE_SCHEMA_VERSION:
            raise ValueError(
                f"model maturation intake must use {MODEL_MATURATION_INTAKE_SCHEMA_VERSION}"
            )
        contributions = tuple(
            item
            if isinstance(item, ModelMaturationCoverageContribution)
            else ModelMaturationCoverageContribution(**dict(item))
            for item in self.contributions
        )
        ids = [item.contribution_id for item in contributions]
        if len(ids) != len(set(ids)):
            raise ValueError("model maturation contribution ids must be unique")
        for item in contributions:
            if item.task_id != self.task_id:
                raise ValueError("model maturation contribution task id mismatch")
        object.__setattr__(self, "contributions", contributions)
        object.__setattr__(self, "required_contribution_ids", _as_tuple(self.required_contribution_ids))
        object.__setattr__(self, "iteration", max(0, int(self.iteration)))
        object.__setattr__(self, "max_iterations", max(1, int(self.max_iterations)))
        object.__setattr__(self, "prior_gap_fingerprints", _as_tuple(self.prior_gap_fingerprints))
        object.__setattr__(self, "prior_state_fingerprints", _as_tuple(self.prior_state_fingerprints))


def compile_model_maturation_plan(intake: ModelMaturationIntake) -> "ModelMaturationPlan":
    """Deterministically union native contributions without reinterpreting them."""

    contribution_ids = {item.contribution_id for item in intake.contributions}
    missing_contributions = tuple(
        item for item in intake.required_contribution_ids if item not in contribution_ids
    )
    coverage_ids = _unique(
        tuple(
            coverage_id
            for contribution in intake.contributions
            for coverage_id in contribution.coverage_ids
        )
        + tuple(f"missing-contribution:{item}" for item in missing_contributions)
    )
    probe_ids = _unique(
        tuple(
            (
                contribution.required_probe_ids[index]
                if index < len(contribution.required_probe_ids)
                else f"probe:{contribution.owner_route}:{coverage_id}"
            )
            for contribution in intake.contributions
            for index, coverage_id in enumerate(contribution.coverage_ids)
        )
        + tuple(f"probe:missing-contribution:{item}" for item in missing_contributions)
    )
    coverage_source_refs = _unique(
        tuple(
            source
            for contribution in intake.contributions
            for source in contribution.coverage_source_refs
        )
        + tuple(
            f"proof:{contribution.evidence_ref.artifact_id}"
            for contribution in intake.contributions
            if contribution.evidence_ref is not None
        )
        + tuple(f"missing:{item}" for item in missing_contributions)
    )
    skeleton = ModelMaturationPlan(
        plan_id=intake.plan_id,
        model_id=intake.model_id,
        risk_id=intake.risk_id,
        task_id=intake.task_id,
        task_purpose=intake.task_purpose,
        coverage_universe_id=f"intake:{intake.intake_id}",
        coverage_owner=f"model_maturation_intake:{intake.intake_id}",
        coverage_source_refs=coverage_source_refs,
        coverage_ids=coverage_ids,
        required_probe_ids=probe_ids,
        iteration=intake.iteration,
        max_iterations=intake.max_iterations,
        prior_gap_fingerprints=intake.prior_gap_fingerprints,
        prior_iteration_fingerprint=intake.prior_iteration_fingerprint,
        prior_candidate_fingerprint=intake.prior_candidate_fingerprint,
        prior_evidence_fingerprint=intake.prior_evidence_fingerprint,
        prior_state_fingerprints=intake.prior_state_fingerprints,
        base_model_fingerprint=intake.base_model_fingerprint,
        candidate_model_fingerprint=intake.candidate_model_fingerprint,
        evidence_fingerprint="pending",
        resolved_gap_receipts=intake.resolved_gap_receipts,
    )
    coverage_fingerprint = skeleton.expected_coverage_fingerprint()
    compiled_signals: list[ModelMaturationSignal] = []
    evidence_identities: list[str] = []
    for contribution in intake.contributions:
        proof = contribution.evidence_ref
        proof_current = contribution.evidence_is_current()
        proof_fingerprint = _stable_fingerprint(proof.to_dict()) if proof else ""
        if proof_fingerprint:
            evidence_identities.append(proof_fingerprint)
        supplied_by_coverage = {signal.coverage_id: signal for signal in contribution.signals}
        for index, coverage_id in enumerate(contribution.coverage_ids):
            probe_id = (
                contribution.required_probe_ids[index]
                if index < len(contribution.required_probe_ids)
                else f"probe:{contribution.owner_route}:{coverage_id}"
            )
            signal = supplied_by_coverage.get(coverage_id)
            if signal is None:
                signal = ModelMaturationSignal(
                    signal_id=f"contribution:{contribution.contribution_id}:{coverage_id}",
                    signal_type=(
                        MODEL_MATURATION_SIGNAL_MISSING_MODEL_OBLIGATION
                        if proof_current
                        else MODEL_MATURATION_SIGNAL_STALE_EVIDENCE
                    ),
                    source_route=contribution.owner_route,
                    coverage_id=coverage_id,
                    probe_id=probe_id,
                    resolution_class=MODEL_MATURATION_RESOLUTION_EVIDENCE_ACQUISITION,
                    prediction=f"{contribution.owner_route} evidence covers {coverage_id}",
                    falsifier=f"current {contribution.owner_route} evidence does not cover {coverage_id}",
                    description=f"typed coverage contribution for {coverage_id}",
                    resolved=proof_current,
                )
            compiled_signals.append(
                replace(
                    signal,
                    source_route=contribution.owner_route,
                    coverage_id=coverage_id,
                    probe_id=signal.probe_id or probe_id,
                    current=proof_current,
                    resolved=bool(signal.resolved and proof_current),
                    evidence_id=proof.artifact_id if proof else signal.evidence_id,
                    evidence_fingerprint=proof_fingerprint or signal.evidence_fingerprint,
                    receipt_id=proof.artifact_id if proof else "",
                    receipt_fingerprint=proof_fingerprint,
                    receipt_status=(MODEL_MATURATION_RECEIPT_STATUS_PASS if proof_current else ""),
                    receipt_task_id=intake.task_id if proof_current else "",
                    receipt_probe_id=(signal.probe_id or probe_id) if proof_current else "",
                    receipt_candidate_fingerprint=(
                        intake.candidate_model_fingerprint if proof_current else ""
                    ),
                    receipt_coverage_fingerprint=coverage_fingerprint if proof_current else "",
                    receipt_evidence_fingerprint=proof_fingerprint if proof_current else "",
                    receipt_owner_route=contribution.owner_route if proof_current else "",
                )
            )
    for contribution_id in missing_contributions:
        coverage_id = f"missing-contribution:{contribution_id}"
        probe_id = f"probe:missing-contribution:{contribution_id}"
        compiled_signals.append(
            ModelMaturationSignal(
                signal_id=coverage_id,
                signal_type=MODEL_MATURATION_SIGNAL_MISSING_MODEL_OBLIGATION,
                source_route="model_maturation_intake",
                coverage_id=coverage_id,
                probe_id=probe_id,
                resolution_class=MODEL_MATURATION_RESOLUTION_EVIDENCE_ACQUISITION,
                prediction=f"required contribution {contribution_id} is present",
                falsifier=f"required contribution {contribution_id} is absent",
                description=f"required native contribution {contribution_id} is missing",
                current=False,
                resolved=False,
            )
        )
    evidence_fingerprint = _stable_fingerprint(
        {"intake_id": intake.intake_id, "evidence": sorted(evidence_identities)}
    )
    return replace(
        skeleton,
        coverage_universe_fingerprint=coverage_fingerprint,
        evidence_fingerprint=evidence_fingerprint,
        signals=tuple(compiled_signals),
    )


@dataclass(frozen=True)
class ModelMaturationIteration:
    """Immutable evidence of one model-review iteration."""

    iteration_id: str
    plan_id: str
    task_id: str
    iteration: int
    base_model_fingerprint: str
    candidate_model_fingerprint: str
    coverage_fingerprint: str
    input_fingerprint: str
    predecessor_iteration_fingerprint: str = ""
    open_gap_fingerprints: tuple[str, ...] = ()
    resolved_gap_fingerprints: tuple[str, ...] = ()
    persisted_gap_fingerprints: tuple[str, ...] = ()
    introduced_gap_fingerprints: tuple[str, ...] = ()
    native_receipt_fingerprints: tuple[str, ...] = ()
    progressed: bool = False
    terminal_reason: str = ""
    next_actions: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "iteration_id", str(self.iteration_id))
        object.__setattr__(self, "plan_id", str(self.plan_id))
        object.__setattr__(self, "task_id", str(self.task_id))
        object.__setattr__(self, "iteration", int(self.iteration))
        object.__setattr__(self, "base_model_fingerprint", str(self.base_model_fingerprint))
        object.__setattr__(self, "candidate_model_fingerprint", str(self.candidate_model_fingerprint))
        object.__setattr__(self, "coverage_fingerprint", str(self.coverage_fingerprint))
        object.__setattr__(self, "input_fingerprint", str(self.input_fingerprint))
        object.__setattr__(self, "predecessor_iteration_fingerprint", str(self.predecessor_iteration_fingerprint))
        object.__setattr__(self, "open_gap_fingerprints", _as_tuple(self.open_gap_fingerprints))
        object.__setattr__(self, "resolved_gap_fingerprints", _as_tuple(self.resolved_gap_fingerprints))
        object.__setattr__(self, "persisted_gap_fingerprints", _as_tuple(self.persisted_gap_fingerprints))
        object.__setattr__(self, "introduced_gap_fingerprints", _as_tuple(self.introduced_gap_fingerprints))
        object.__setattr__(self, "native_receipt_fingerprints", _as_tuple(self.native_receipt_fingerprints))
        object.__setattr__(self, "progressed", bool(self.progressed))
        object.__setattr__(self, "terminal_reason", str(self.terminal_reason))
        object.__setattr__(self, "next_actions", _as_tuple(self.next_actions))

    def to_dict(self) -> dict[str, Any]:
        return {
            "iteration_id": self.iteration_id,
            "plan_id": self.plan_id,
            "task_id": self.task_id,
            "iteration": self.iteration,
            "base_model_fingerprint": self.base_model_fingerprint,
            "candidate_model_fingerprint": self.candidate_model_fingerprint,
            "coverage_fingerprint": self.coverage_fingerprint,
            "input_fingerprint": self.input_fingerprint,
            "predecessor_iteration_fingerprint": self.predecessor_iteration_fingerprint,
            "open_gap_fingerprints": list(self.open_gap_fingerprints),
            "resolved_gap_fingerprints": list(self.resolved_gap_fingerprints),
            "persisted_gap_fingerprints": list(self.persisted_gap_fingerprints),
            "introduced_gap_fingerprints": list(self.introduced_gap_fingerprints),
            "native_receipt_fingerprints": list(self.native_receipt_fingerprints),
            "progressed": self.progressed,
            "terminal_reason": self.terminal_reason,
            "next_actions": list(self.next_actions),
            "iteration_fingerprint": self.fingerprint(),
        }

    def fingerprint(self) -> str:
        value = {
            "iteration_id": self.iteration_id,
            "plan_id": self.plan_id,
            "task_id": self.task_id,
            "iteration": self.iteration,
            "base_model_fingerprint": self.base_model_fingerprint,
            "candidate_model_fingerprint": self.candidate_model_fingerprint,
            "coverage_fingerprint": self.coverage_fingerprint,
            "input_fingerprint": self.input_fingerprint,
            "predecessor_iteration_fingerprint": self.predecessor_iteration_fingerprint,
            "open_gap_fingerprints": list(self.open_gap_fingerprints),
            "resolved_gap_fingerprints": list(self.resolved_gap_fingerprints),
            "persisted_gap_fingerprints": list(self.persisted_gap_fingerprints),
            "introduced_gap_fingerprints": list(self.introduced_gap_fingerprints),
            "native_receipt_fingerprints": list(self.native_receipt_fingerprints),
            "progressed": self.progressed,
            "terminal_reason": self.terminal_reason,
            "next_actions": list(self.next_actions),
        }
        return _stable_fingerprint(value)


@dataclass(frozen=True)
class ModelMaturationSession:
    """A sequence of immutable iterations for one task-local model review."""

    session_id: str
    task_id: str
    iterations: tuple[ModelMaturationIteration, ...] = ()
    terminal_reason: str = ""
    findings: tuple["ModelMaturationFinding", ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "session_id", str(self.session_id))
        object.__setattr__(self, "task_id", str(self.task_id))
        object.__setattr__(self, "iterations", tuple(self.iterations))
        object.__setattr__(self, "terminal_reason", str(self.terminal_reason))
        object.__setattr__(self, "findings", tuple(self.findings))

    @property
    def closed(self) -> bool:
        return self.terminal_reason == MODEL_MATURATION_DECISION_CLOSED_FOR_TASK

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "task_id": self.task_id,
            "iterations": [item.to_dict() for item in self.iterations],
            "terminal_reason": self.terminal_reason,
            "closed": self.closed,
            "ok": self.closed and not self.findings,
            "findings": [item.to_dict() for item in self.findings],
        }


@dataclass(frozen=True)
class ModelMaturationFinding:
    """One model maturation loop diagnostic."""

    code: str
    message: str
    severity: str = "blocker"
    signal_id: str = ""
    model_id: str = ""
    risk_id: str = ""
    action: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "code", str(self.code))
        object.__setattr__(self, "message", str(self.message))
        object.__setattr__(self, "severity", str(self.severity))
        object.__setattr__(self, "signal_id", str(self.signal_id))
        object.__setattr__(self, "model_id", str(self.model_id))
        object.__setattr__(self, "risk_id", str(self.risk_id))
        object.__setattr__(self, "action", str(self.action))
        object.__setattr__(self, "metadata", dict(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "severity": self.severity,
            "signal_id": self.signal_id,
            "model_id": self.model_id,
            "risk_id": self.risk_id,
            "action": self.action,
            "metadata": to_jsonable(dict(self.metadata)),
        }


@dataclass(frozen=True)
class ModelMaturationPlan:
    """Inputs for a model maturation review."""

    plan_id: str
    schema_version: str = MODEL_MATURATION_PLAN_SCHEMA_VERSION
    model_id: str = ""
    risk_id: str = ""
    signals: tuple[ModelMaturationSignal, ...] = ()
    task_id: str = ""
    task_purpose: str = ""
    coverage_universe_id: str = ""
    coverage_universe_fingerprint: str = ""
    coverage_owner: str = ""
    coverage_source_refs: tuple[str, ...] = ()
    coverage_ids: tuple[str, ...] = ()
    required_probe_ids: tuple[str, ...] = ()
    iteration: int = 0
    max_iterations: int = 8
    prior_gap_fingerprints: tuple[str, ...] = ()
    prior_iteration_fingerprint: str = ""
    prior_candidate_fingerprint: str = ""
    prior_evidence_fingerprint: str = ""
    prior_state_fingerprints: tuple[str, ...] = ()
    base_model_fingerprint: str = ""
    candidate_model_fingerprint: str = ""
    evidence_fingerprint: str = ""
    resolved_gap_receipts: Mapping[str, ModelMaturationGapResolutionReceipt] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "plan_id", str(self.plan_id))
        object.__setattr__(self, "schema_version", str(self.schema_version))
        object.__setattr__(self, "model_id", str(self.model_id))
        object.__setattr__(self, "risk_id", str(self.risk_id))
        object.__setattr__(self, "signals", tuple(self.signals))
        object.__setattr__(self, "task_id", str(self.task_id))
        object.__setattr__(self, "task_purpose", str(self.task_purpose))
        object.__setattr__(self, "coverage_universe_id", str(self.coverage_universe_id))
        object.__setattr__(self, "coverage_universe_fingerprint", str(self.coverage_universe_fingerprint))
        object.__setattr__(self, "coverage_owner", str(self.coverage_owner))
        object.__setattr__(self, "coverage_source_refs", _as_tuple(self.coverage_source_refs))
        object.__setattr__(self, "coverage_ids", _as_tuple(self.coverage_ids))
        object.__setattr__(self, "required_probe_ids", _as_tuple(self.required_probe_ids))
        object.__setattr__(self, "iteration", max(0, int(self.iteration)))
        object.__setattr__(self, "max_iterations", max(1, int(self.max_iterations)))
        object.__setattr__(self, "prior_gap_fingerprints", _as_tuple(self.prior_gap_fingerprints))
        object.__setattr__(self, "prior_iteration_fingerprint", str(self.prior_iteration_fingerprint))
        object.__setattr__(self, "prior_candidate_fingerprint", str(self.prior_candidate_fingerprint))
        object.__setattr__(self, "prior_evidence_fingerprint", str(self.prior_evidence_fingerprint))
        object.__setattr__(self, "prior_state_fingerprints", _as_tuple(self.prior_state_fingerprints))
        object.__setattr__(self, "base_model_fingerprint", str(self.base_model_fingerprint))
        object.__setattr__(self, "candidate_model_fingerprint", str(self.candidate_model_fingerprint))
        object.__setattr__(self, "evidence_fingerprint", str(self.evidence_fingerprint))
        normalized_receipts: dict[str, ModelMaturationGapResolutionReceipt] = {}
        for key, value in self.resolved_gap_receipts.items():
            if isinstance(value, ModelMaturationGapResolutionReceipt):
                receipt = value
            elif isinstance(value, Mapping):
                receipt = ModelMaturationGapResolutionReceipt.from_dict(value)
            else:
                raise ValueError("resolved gap receipts must be typed current receipt records")
            normalized_receipts[str(key)] = receipt
        object.__setattr__(self, "resolved_gap_receipts", normalized_receipts)

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "ModelMaturationPlan":
        allowed = {
            "plan_id", "schema_version", "model_id", "risk_id", "signals",
            "task_id", "task_purpose", "coverage_universe_id",
            "coverage_universe_fingerprint", "coverage_owner",
            "coverage_source_refs", "coverage_ids", "required_probe_ids",
            "iteration", "max_iterations", "prior_gap_fingerprints",
            "prior_iteration_fingerprint", "prior_candidate_fingerprint",
            "prior_evidence_fingerprint", "prior_state_fingerprints",
            "base_model_fingerprint", "candidate_model_fingerprint",
            "evidence_fingerprint", "resolved_gap_receipts",
        }
        unknown = sorted(set(value) - allowed)
        if unknown:
            raise ValueError(f"unknown model maturation plan fields: {unknown}")
        schema_version = str(value.get("schema_version", ""))
        if schema_version != MODEL_MATURATION_PLAN_SCHEMA_VERSION:
            raise ValueError(
                f"model maturation payload must use {MODEL_MATURATION_PLAN_SCHEMA_VERSION}; "
                "former or missing schema versions are not accepted"
            )
        signals = value.get("signals", ())
        return cls(
            plan_id=str(value.get("plan_id", "")),
            schema_version=schema_version,
            model_id=str(value.get("model_id", "")),
            risk_id=str(value.get("risk_id", "")),
            signals=tuple(ModelMaturationSignal.from_dict(item) for item in signals if isinstance(item, Mapping)),
            task_id=str(value.get("task_id", "")),
            task_purpose=str(value.get("task_purpose", "")),
            coverage_universe_id=str(value.get("coverage_universe_id", "")),
            coverage_universe_fingerprint=str(value.get("coverage_universe_fingerprint", "")),
            coverage_owner=str(value.get("coverage_owner", "")),
            coverage_source_refs=tuple(value.get("coverage_source_refs", ())),
            coverage_ids=tuple(value.get("coverage_ids", ())),
            required_probe_ids=tuple(value.get("required_probe_ids", ())),
            iteration=int(value.get("iteration", 0)),
            max_iterations=int(value.get("max_iterations", 8)),
            prior_gap_fingerprints=tuple(value.get("prior_gap_fingerprints", ())),
            prior_iteration_fingerprint=str(value.get("prior_iteration_fingerprint", "")),
            prior_candidate_fingerprint=str(value.get("prior_candidate_fingerprint", "")),
            prior_evidence_fingerprint=str(value.get("prior_evidence_fingerprint", "")),
            prior_state_fingerprints=tuple(value.get("prior_state_fingerprints", ())),
            base_model_fingerprint=str(value.get("base_model_fingerprint", "")),
            candidate_model_fingerprint=str(value.get("candidate_model_fingerprint", "")),
            evidence_fingerprint=str(value.get("evidence_fingerprint", "")),
            resolved_gap_receipts=value.get("resolved_gap_receipts", {}) if isinstance(value.get("resolved_gap_receipts", {}), Mapping) else {},
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "schema_version": self.schema_version,
            "model_id": self.model_id,
            "risk_id": self.risk_id,
            "signals": [signal.to_dict() for signal in self.signals],
            "task_id": self.task_id,
            "task_purpose": self.task_purpose,
            "coverage_universe_id": self.coverage_universe_id,
            "coverage_universe_fingerprint": self.coverage_universe_fingerprint,
            "coverage_owner": self.coverage_owner,
            "coverage_source_refs": list(self.coverage_source_refs),
            "coverage_ids": list(self.coverage_ids),
            "required_probe_ids": list(self.required_probe_ids),
            "iteration": self.iteration,
            "max_iterations": self.max_iterations,
            "prior_gap_fingerprints": list(self.prior_gap_fingerprints),
            "prior_iteration_fingerprint": self.prior_iteration_fingerprint,
            "prior_candidate_fingerprint": self.prior_candidate_fingerprint,
            "prior_evidence_fingerprint": self.prior_evidence_fingerprint,
            "prior_state_fingerprints": list(self.prior_state_fingerprints),
            "base_model_fingerprint": self.base_model_fingerprint,
            "candidate_model_fingerprint": self.candidate_model_fingerprint,
            "evidence_fingerprint": self.evidence_fingerprint,
            "resolved_gap_receipts": {
                gap: receipt.to_dict()
                for gap, receipt in self.resolved_gap_receipts.items()
            },
        }

    def expected_coverage_fingerprint(self) -> str:
        return _stable_fingerprint(
            {
                "coverage_universe_id": self.coverage_universe_id,
                "coverage_owner": self.coverage_owner,
                "coverage_source_refs": list(self.coverage_source_refs),
                "coverage_ids": list(self.coverage_ids),
                "required_probe_ids": list(self.required_probe_ids),
            }
        )


@dataclass(frozen=True)
class ModelMaturationReport:
    """Result of a model maturation review."""

    ok: bool
    plan_id: str
    decision: str
    confidence: str
    model_id: str = ""
    risk_id: str = ""
    recommended_actions: tuple[str, ...] = ()
    findings: tuple[ModelMaturationFinding, ...] = ()
    scoped_signal_ids: tuple[str, ...] = ()
    maintenance_obligations: tuple[MaintenanceObligation, ...] = ()
    summary: str = ""
    task_id: str = ""
    coverage_universe_id: str = ""
    coverage_universe_fingerprint: str = ""
    base_model_fingerprint: str = ""
    candidate_model_fingerprint: str = ""
    evidence_fingerprint: str = ""
    evidence_id: str = ""
    iteration: int = 0
    terminal_reason: str = ""
    next_actions: tuple[str, ...] = ()
    open_gap_fingerprints: tuple[str, ...] = ()
    input_fingerprint: str = ""
    progressed: bool = False
    iteration_record: ModelMaturationIteration | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "plan_id", str(self.plan_id))
        object.__setattr__(self, "decision", str(self.decision))
        object.__setattr__(self, "confidence", str(self.confidence))
        object.__setattr__(self, "model_id", str(self.model_id))
        object.__setattr__(self, "risk_id", str(self.risk_id))
        object.__setattr__(self, "recommended_actions", _as_tuple(self.recommended_actions))
        object.__setattr__(self, "findings", tuple(self.findings))
        object.__setattr__(self, "scoped_signal_ids", _as_tuple(self.scoped_signal_ids))
        obligations = self.maintenance_obligations or obligations_from_maturation_findings(self.findings)
        object.__setattr__(
            self,
            "maintenance_obligations",
            tuple(coerce_maintenance_obligation(item) for item in obligations),
        )
        object.__setattr__(self, "summary", str(self.summary))
        object.__setattr__(self, "task_id", str(self.task_id))
        object.__setattr__(self, "coverage_universe_id", str(self.coverage_universe_id))
        object.__setattr__(
            self, "coverage_universe_fingerprint", str(self.coverage_universe_fingerprint)
        )
        object.__setattr__(self, "base_model_fingerprint", str(self.base_model_fingerprint))
        object.__setattr__(
            self, "candidate_model_fingerprint", str(self.candidate_model_fingerprint)
        )
        object.__setattr__(self, "evidence_fingerprint", str(self.evidence_fingerprint))
        object.__setattr__(self, "evidence_id", str(self.evidence_id))
        object.__setattr__(self, "iteration", int(self.iteration))
        terminal = str(self.terminal_reason)
        if terminal and terminal not in MODEL_MATURATION_TERMINAL_REASONS:
            raise ValueError(f"unknown model maturation terminal reason: {terminal}")
        object.__setattr__(self, "terminal_reason", terminal)
        object.__setattr__(self, "next_actions", _as_tuple(self.next_actions or self.recommended_actions))
        object.__setattr__(self, "open_gap_fingerprints", _as_tuple(self.open_gap_fingerprints))
        object.__setattr__(self, "input_fingerprint", str(self.input_fingerprint))
        object.__setattr__(self, "progressed", bool(self.progressed))

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "plan_id": self.plan_id,
            "decision": self.decision,
            "confidence": self.confidence,
            "model_id": self.model_id,
            "risk_id": self.risk_id,
            "recommended_actions": list(self.recommended_actions),
            "findings": [finding.to_dict() for finding in self.findings],
            "scoped_signal_ids": list(self.scoped_signal_ids),
            "maintenance_obligations": [obligation.to_dict() for obligation in self.maintenance_obligations],
            "summary": self.summary,
            "task_id": self.task_id,
            "coverage_universe_id": self.coverage_universe_id,
            "coverage_universe_fingerprint": self.coverage_universe_fingerprint,
            "base_model_fingerprint": self.base_model_fingerprint,
            "candidate_model_fingerprint": self.candidate_model_fingerprint,
            "evidence_fingerprint": self.evidence_fingerprint,
            "evidence_id": self.evidence_id,
            "iteration": self.iteration,
            "terminal_reason": self.terminal_reason,
            "next_actions": list(self.next_actions),
            "open_gap_fingerprints": list(self.open_gap_fingerprints),
            "input_fingerprint": self.input_fingerprint,
            "progressed": self.progressed,
            "iteration_record": self.iteration_record.to_dict() if self.iteration_record else None,
        }

    def format_text(self) -> str:
        lines = [
            f"FlowGuard model maturation loop: {self.decision}",
            f"confidence: {self.confidence}",
        ]
        if self.model_id:
            lines.append(f"model: {self.model_id}")
        if self.risk_id:
            lines.append(f"risk: {self.risk_id}")
        if self.recommended_actions:
            lines.append("recommended actions:")
            lines.extend(f"- {action}" for action in self.recommended_actions)
        if self.findings:
            lines.append("findings:")
            lines.extend(
                f"- [{finding.severity}] {finding.code}: {finding.message}"
                for finding in self.findings
            )
        if self.maintenance_obligations:
            lines.append("maintenance obligations:")
            lines.extend(
                f"- {obligation.status} {obligation.strength}: {obligation.obligation_id}"
                for obligation in self.maintenance_obligations
            )
        if self.summary:
            lines.append(self.summary)
        if self.task_id:
            lines.append(f"task: {self.task_id} iteration: {self.iteration}")
        if self.terminal_reason:
            lines.append(f"terminal reason: {self.terminal_reason}")
        if self.next_actions:
            lines.append("next actions:")
            lines.extend(f"- {action}" for action in self.next_actions)
        return "\n".join(lines)


@dataclass(frozen=True)
class ModelMaturationEvidenceRef:
    """Compact exact identity consumed by admission, risk, and closure."""

    evidence_id: str
    task_id: str
    model_id: str
    candidate_model_fingerprint: str
    coverage_universe_id: str
    coverage_universe_fingerprint: str
    input_fingerprint: str
    evidence_fingerprint: str
    decision: str
    confidence: str
    terminal_reason: str
    open_gap_fingerprints: tuple[str, ...] = ()
    current: bool = True

    def __post_init__(self) -> None:
        for name in (
            "evidence_id",
            "task_id",
            "model_id",
            "candidate_model_fingerprint",
            "coverage_universe_id",
            "coverage_universe_fingerprint",
            "input_fingerprint",
            "evidence_fingerprint",
            "decision",
            "confidence",
            "terminal_reason",
        ):
            object.__setattr__(self, name, str(getattr(self, name)))
        object.__setattr__(self, "open_gap_fingerprints", _as_tuple(self.open_gap_fingerprints))
        object.__setattr__(self, "current", bool(self.current))

    @classmethod
    def from_report(cls, report: ModelMaturationReport) -> "ModelMaturationEvidenceRef":
        required_identity = all(
            (
                report.evidence_id,
                report.task_id,
                report.model_id,
                report.candidate_model_fingerprint,
                report.coverage_universe_id,
                report.coverage_universe_fingerprint,
                report.input_fingerprint,
                report.evidence_fingerprint,
            )
        )
        return cls(
            evidence_id=report.evidence_id,
            task_id=report.task_id,
            model_id=report.model_id,
            candidate_model_fingerprint=report.candidate_model_fingerprint,
            coverage_universe_id=report.coverage_universe_id,
            coverage_universe_fingerprint=report.coverage_universe_fingerprint,
            input_fingerprint=report.input_fingerprint,
            evidence_fingerprint=report.evidence_fingerprint,
            decision=report.decision,
            confidence=report.confidence,
            terminal_reason=report.terminal_reason,
            open_gap_fingerprints=report.open_gap_fingerprints,
            current=bool(required_identity),
        )

    def supports_full_confidence(self) -> bool:
        return bool(
            self.current
            and self.decision == MODEL_MATURATION_DECISION_CLOSED_FOR_TASK
            and self.confidence == MODEL_MATURATION_CONFIDENCE_FULL
            and self.terminal_reason == MODEL_MATURATION_DECISION_CLOSED_FOR_TASK
            and not self.open_gap_fingerprints
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "evidence_id": self.evidence_id,
            "task_id": self.task_id,
            "model_id": self.model_id,
            "candidate_model_fingerprint": self.candidate_model_fingerprint,
            "coverage_universe_id": self.coverage_universe_id,
            "coverage_universe_fingerprint": self.coverage_universe_fingerprint,
            "input_fingerprint": self.input_fingerprint,
            "evidence_fingerprint": self.evidence_fingerprint,
            "decision": self.decision,
            "confidence": self.confidence,
            "terminal_reason": self.terminal_reason,
            "open_gap_fingerprints": list(self.open_gap_fingerprints),
            "current": self.current,
        }


def coerce_model_maturation_evidence_ref(
    value: ModelMaturationEvidenceRef | Mapping[str, Any] | None,
) -> ModelMaturationEvidenceRef | None:
    if value is None or isinstance(value, ModelMaturationEvidenceRef):
        return value
    return ModelMaturationEvidenceRef(**dict(value))


def _signal_finding(
    code: str,
    message: str,
    *,
    signal: ModelMaturationSignal,
    severity: str = "blocker",
    action: str = "",
) -> ModelMaturationFinding:
    return ModelMaturationFinding(
        code=code,
        message=message,
        severity=severity,
        signal_id=signal.signal_id,
        model_id=signal.model_id,
        risk_id=signal.risk_id,
        action=action,
        metadata=signal.to_dict(),
    )


def _plan_finding(code: str, message: str, *, action: str = MATURITY_ACTION_ADD_MODEL_OBLIGATION) -> ModelMaturationFinding:
    return ModelMaturationFinding(code=code, message=message, action=action)


def _contract_gap(code: str) -> str:
    return _stable_fingerprint({"contract_gap": code})


def _iteration_for(
    plan: ModelMaturationPlan,
    *,
    open_gap_fingerprints: Sequence[str],
    resolved_gap_fingerprints: Sequence[str],
    persisted_gap_fingerprints: Sequence[str],
    introduced_gap_fingerprints: Sequence[str],
    native_receipt_fingerprints: Sequence[str],
    progressed: bool,
    decision: str,
    recommended: Sequence[str],
) -> ModelMaturationIteration:
    input_fingerprint = _stable_fingerprint(plan.to_dict())
    terminal_reason = decision if decision in MODEL_MATURATION_TERMINAL_REASONS else ""
    return ModelMaturationIteration(
        iteration_id=f"{plan.plan_id}:{plan.iteration}",
        plan_id=plan.plan_id,
        task_id=plan.task_id,
        iteration=plan.iteration,
        base_model_fingerprint=plan.base_model_fingerprint,
        candidate_model_fingerprint=plan.candidate_model_fingerprint,
        coverage_fingerprint=plan.coverage_universe_fingerprint,
        input_fingerprint=input_fingerprint,
        predecessor_iteration_fingerprint=plan.prior_iteration_fingerprint,
        open_gap_fingerprints=tuple(sorted(set(open_gap_fingerprints))),
        resolved_gap_fingerprints=tuple(sorted(set(resolved_gap_fingerprints))),
        persisted_gap_fingerprints=tuple(sorted(set(persisted_gap_fingerprints))),
        introduced_gap_fingerprints=tuple(sorted(set(introduced_gap_fingerprints))),
        native_receipt_fingerprints=tuple(sorted(set(native_receipt_fingerprints))),
        progressed=progressed,
        terminal_reason=terminal_reason,
        next_actions=_unique(recommended),
    )


def review_model_maturation_loop(plan: ModelMaturationPlan) -> ModelMaturationReport:
    """Review one task-local iteration and require executable closure.

    The function deliberately does not ask the model whether it understood
    anything.  A gap closes only when the route supplies a current signal with
    a prediction/falsifier or an explicit external/scope disposition.  A later
    call with the next candidate model is the next iteration.
    """

    findings: list[ModelMaturationFinding] = []
    recommended_actions: list[str] = []
    scoped_signal_ids: list[str] = []
    external_signal_ids: list[str] = []
    open_gap_fingerprints: list[str] = []
    normalized_signals: list[ModelMaturationSignal] = []
    native_receipt_fingerprints: list[str] = []
    progress_receipt_fingerprints: list[str] = []
    verified_coverage_ids: set[str] = set()
    represented_coverage_ids: set[str] = set()
    seen_probe_ids: set[str] = set()

    required_text = {
        "missing_plan_id": plan.plan_id,
        "missing_task_id": plan.task_id,
        "missing_task_purpose": plan.task_purpose,
        "missing_coverage_universe_id": plan.coverage_universe_id,
        "missing_coverage_universe_fingerprint": plan.coverage_universe_fingerprint,
        "missing_coverage_owner": plan.coverage_owner,
        "missing_base_model_fingerprint": plan.base_model_fingerprint,
        "missing_candidate_model_fingerprint": plan.candidate_model_fingerprint,
        "missing_evidence_fingerprint": plan.evidence_fingerprint,
    }
    if plan.schema_version != MODEL_MATURATION_PLAN_SCHEMA_VERSION:
        findings.append(_plan_finding("current_schema_required", f"plan must use {MODEL_MATURATION_PLAN_SCHEMA_VERSION}"))
    for code, value in required_text.items():
        if not str(value).strip():
            findings.append(_plan_finding(code, code.replace("_", " ")))
    if not plan.coverage_source_refs:
        findings.append(_plan_finding("missing_coverage_source_refs", "independent coverage source references are required"))
    if not plan.coverage_ids:
        findings.append(_plan_finding("missing_coverage_universe", "the independent coverage universe is empty"))
    if not plan.required_probe_ids:
        findings.append(_plan_finding("missing_required_probes", "the required native probe inventory is empty"))
    if plan.coverage_universe_fingerprint and plan.coverage_universe_fingerprint != plan.expected_coverage_fingerprint():
        findings.append(_plan_finding("coverage_universe_fingerprint_mismatch", "coverage universe fingerprint does not match its owner, sources, coverage, and probes"))
    if plan.iteration > 0:
        if not plan.prior_iteration_fingerprint:
            findings.append(_plan_finding("missing_predecessor_iteration", "a later iteration requires the exact predecessor fingerprint"))
        if not plan.prior_candidate_fingerprint:
            findings.append(_plan_finding("missing_prior_candidate", "a later iteration requires the preceding candidate identity"))
        elif plan.base_model_fingerprint != plan.prior_candidate_fingerprint:
            findings.append(_plan_finding("candidate_chain_mismatch", "the current base model is not the preceding candidate"))
    for finding in findings:
        recommended_actions.append(finding.action or MATURITY_ACTION_ADD_MODEL_OBLIGATION)
        open_gap_fingerprints.append(_contract_gap(finding.code))

    for original in plan.signals:
        signal = original
        if not signal.model_id or not signal.risk_id:
            signal = replace(
                signal,
                model_id=signal.model_id or plan.model_id,
                risk_id=signal.risk_id or plan.risk_id,
            )
        normalized_signals.append(signal)
        if signal.coverage_id in plan.coverage_ids:
            represented_coverage_ids.add(signal.coverage_id)

        if signal.metadata.get("understood") is not None or signal.metadata.get("understanding_level") is not None:
            findings.append(
                _signal_finding(
                    "self_report_not_evidence",
                    "a self-reported understanding field is not executable evidence",
                    signal=signal,
                    action=MATURITY_ACTION_ADD_MODEL_OBLIGATION,
                )
            )
            recommended_actions.append(MATURITY_ACTION_ADD_MODEL_OBLIGATION)

        if signal.required:
            if not signal.coverage_id or signal.coverage_id not in plan.coverage_ids:
                findings.append(_signal_finding("signal_coverage_not_in_universe", "required signal is not bound to the independent coverage universe", signal=signal))
            if not signal.probe_id or signal.probe_id not in plan.required_probe_ids:
                findings.append(_signal_finding("signal_probe_not_required", "required signal is not bound to the frozen required-probe inventory", signal=signal))
            else:
                seen_probe_ids.add(signal.probe_id)
            if not signal.prediction.strip():
                findings.append(_signal_finding("missing_signal_prediction", "required signal has no pre-observation prediction", signal=signal))
            if not signal.falsifier.strip():
                findings.append(_signal_finding("missing_signal_falsifier", "required signal has no falsifier", signal=signal))

        raw_resolution = signal.resolution_class
        if raw_resolution not in MODEL_MATURATION_RESOLUTION_CLASSES:
            findings.append(_signal_finding("invalid_resolution_class", "required signal must declare one current resolution class", signal=signal))
            raw_resolution = MODEL_MATURATION_RESOLUTION_MODEL_EDIT
        resolution = raw_resolution
        if not signal.in_scope:
            if resolution == MODEL_MATURATION_RESOLUTION_SCOPE_EXCLUDED:
                scoped_signal_ids.append(signal.signal_id)
            elif signal.required:
                findings.append(
                    _signal_finding(
                        "model_maturation_signal_out_of_scope",
                        "a required signal was scoped out without an explicit scope disposition",
                        signal=signal,
                        action=MATURITY_ACTION_DOWNGRADE_CLAIM,
                    )
                )
                open_gap_fingerprints.append(signal.gap_fingerprint())
                recommended_actions.append(MATURITY_ACTION_DOWNGRADE_CLAIM)
            continue

        if signal.signal_type not in MODEL_MATURATION_SIGNAL_TYPES:
            findings.append(
                _signal_finding(
                    "unknown_model_maturation_signal",
                    "maturation signal type is unknown and cannot support full confidence",
                    signal=signal,
                    action=MATURITY_ACTION_ADD_MODEL_OBLIGATION,
                )
            )
            recommended_actions.append(MATURITY_ACTION_ADD_MODEL_OBLIGATION)
            if signal.required:
                open_gap_fingerprints.append(signal.gap_fingerprint())

        evidence_verified = signal.evidence_receipt_is_verified(
            task_id=plan.task_id,
            candidate_fingerprint=plan.candidate_model_fingerprint,
            coverage_fingerprint=plan.coverage_universe_fingerprint,
        )
        verified = signal.resolved and evidence_verified
        if signal.resolved and not verified:
            findings.append(
                _signal_finding(
                    "unverified_signal_resolution",
                    "caller-authored resolution is not accepted without an exact current terminal receipt",
                    signal=signal,
                    action=MATURITY_ACTION_REFRESH_EVIDENCE,
                )
            )
            recommended_actions.append(MATURITY_ACTION_REFRESH_EVIDENCE)
        if evidence_verified:
            native_receipt_fingerprints.append(signal.receipt_fingerprint)
            progress_receipt_fingerprints.append(signal.receipt_fingerprint)
        if verified:
            if signal.coverage_id:
                verified_coverage_ids.add(signal.coverage_id)
            continue
        if signal.required and not signal.current:
            findings.append(
                _signal_finding(
                    "model_maturation_signal_stale",
                    "required signal lacks current evidence and cannot support task closure",
                    signal=signal,
                    action=MATURITY_ACTION_REFRESH_EVIDENCE,
                )
            )
            recommended_actions.append(MATURITY_ACTION_REFRESH_EVIDENCE)

        signal_actions = signal.actions()
        recommended_actions.extend(signal_actions)
        if resolution == MODEL_MATURATION_RESOLUTION_EXTERNAL_INPUT_REQUIRED:
            if not signal.required_input or not signal.owner_boundary or not signal.affected_claim_scope:
                findings.append(
                    _signal_finding(
                        "incomplete_external_input_boundary",
                        "external termination requires the exact input, owner boundary, and affected claim scope",
                        signal=signal,
                        action=MATURITY_ACTION_REFRESH_EVIDENCE,
                    )
                )
            external_signal_ids.append(signal.signal_id)
            findings.append(
                _signal_finding(
                    "external_input_required",
                    "the next model-discriminating observation belongs to an external provider or operator",
                    signal=signal,
                    action=MATURITY_ACTION_REFRESH_EVIDENCE,
                )
            )
            open_gap_fingerprints.append(signal.gap_fingerprint())
        elif resolution == MODEL_MATURATION_RESOLUTION_SCOPE_EXCLUDED:
            scoped_signal_ids.append(signal.signal_id)
            findings.append(
                _signal_finding(
                    "scope_excluded",
                    "this signal is explicitly outside the declared task boundary",
                    signal=signal,
                    severity="warning",
                    action=MATURITY_ACTION_DOWNGRADE_CLAIM,
                )
            )
            recommended_actions.append(MATURITY_ACTION_DOWNGRADE_CLAIM)
        elif signal.required:
            for action in signal_actions:
                findings.append(
                    _signal_finding(
                        "model_upgrade_required",
                        "an unresolved addressable signal requires another model/evidence iteration",
                        signal=signal,
                        action=action,
                    )
                )
            open_gap_fingerprints.append(signal.gap_fingerprint())
        else:
            findings.append(
                _signal_finding(
                    "optional_model_maturation_signal_open",
                    "optional signal remains open and must be tracked as scoped evidence",
                    signal=signal,
                    severity="warning",
                    action=MATURITY_ACTION_DOWNGRADE_CLAIM,
                )
            )
            scoped_signal_ids.append(signal.signal_id)
            recommended_actions.append(MATURITY_ACTION_DOWNGRADE_CLAIM)

    for probe_id in plan.required_probe_ids:
        if probe_id not in seen_probe_ids:
            finding = _plan_finding("missing_required_probe_signal", f"required probe {probe_id} has no task-local signal")
            findings.append(finding)
            recommended_actions.append(finding.action)
            open_gap_fingerprints.append(_stable_fingerprint({"missing_probe": probe_id}))

    if plan.coverage_ids:
        externally_disposed = {
            signal.coverage_id
            for signal in normalized_signals
            if signal.coverage_id
            and not signal.receipt_is_verified(
                task_id=plan.task_id,
                candidate_fingerprint=plan.candidate_model_fingerprint,
                coverage_fingerprint=plan.coverage_universe_fingerprint,
            )
            and signal.resolution() in {
                MODEL_MATURATION_RESOLUTION_EXTERNAL_INPUT_REQUIRED,
                MODEL_MATURATION_RESOLUTION_SCOPE_EXCLUDED,
            }
        }
        for coverage_id in plan.coverage_ids:
            if (
                coverage_id not in represented_coverage_ids
                and coverage_id not in verified_coverage_ids
                and coverage_id not in externally_disposed
            ):
                coverage_signal = ModelMaturationSignal(
                    signal_id=f"coverage:{coverage_id}",
                    signal_type=MODEL_MATURATION_SIGNAL_MISSING_MODEL_OBLIGATION,
                    model_id=plan.model_id,
                    risk_id=plan.risk_id,
                    coverage_id=coverage_id,
                    description=f"declared coverage item {coverage_id} has no resolved native evidence",
                )
                findings.append(
                    _signal_finding(
                        "missing_model_coverage",
                        coverage_signal.description,
                        signal=coverage_signal,
                        action=MATURITY_ACTION_ADD_MODEL_OBLIGATION,
                    )
                )
                recommended_actions.append(MATURITY_ACTION_ADD_MODEL_OBLIGATION)
                open_gap_fingerprints.append(coverage_signal.gap_fingerprint())

    previous = set(plan.prior_gap_fingerprints)
    current = set(open_gap_fingerprints)
    candidate_resolved = previous - current
    verified_resolved: set[str] = set()
    for gap in sorted(candidate_resolved):
        receipt = plan.resolved_gap_receipts.get(gap)
        if receipt is not None and receipt.is_verified(
            gap_fingerprint=gap,
            task_id=plan.task_id,
            candidate_fingerprint=plan.candidate_model_fingerprint,
            coverage_fingerprint=plan.coverage_universe_fingerprint,
        ):
            verified_resolved.add(gap)
            native_receipt_fingerprints.append(receipt.receipt_fingerprint)
        else:
            current.add(gap)
            finding = _plan_finding("gap_deleted_without_resolution_receipt", "a prior gap disappeared without a current resolution receipt", action=MATURITY_ACTION_REFRESH_EVIDENCE)
            findings.append(finding)
            recommended_actions.append(finding.action)
    resolved = verified_resolved
    persisted = previous & current
    introduced = current - previous
    evidence_advanced = bool(plan.prior_evidence_fingerprint and plan.evidence_fingerprint != plan.prior_evidence_fingerprint)
    progressed = (
        plan.iteration == 0
        or bool(resolved)
        or (evidence_advanced and bool(progress_receipt_fingerprints))
    )
    state_fingerprint = _stable_fingerprint(
        {
            "candidate": plan.candidate_model_fingerprint,
            "evidence": plan.evidence_fingerprint,
            "open_gaps": sorted(current),
        }
    )
    oscillating = plan.iteration > 0 and state_fingerprint in set(plan.prior_state_fingerprints)
    if oscillating:
        finding = _plan_finding(
            "model_maturation_oscillation",
            "the candidate, evidence, and open-gap state repeats an earlier iteration",
            action=MATURITY_ACTION_REFRESH_EVIDENCE,
        )
        findings.append(finding)
        recommended_actions.append(finding.action)

    recommended = _unique(recommended_actions)
    scoped_ids = _unique(scoped_signal_ids)
    blockers = [finding for finding in findings if finding.severity == "blocker"]
    addressable = [
        finding for finding in blockers
        if finding.code not in {"external_input_required"}
    ]
    if not current and not blockers and not scoped_ids and len(verified_coverage_ids) == len(set(plan.coverage_ids)):
        decision = MODEL_MATURATION_DECISION_CLOSED_FOR_TASK
        confidence = MODEL_MATURATION_CONFIDENCE_FULL
        ok = True
        summary = "All independently declared task coverage is closed by exact current native receipts."
        recommended = recommended or (MATURITY_ACTION_NO_CHANGE,)
    elif external_signal_ids and not addressable and not any(item.code == "incomplete_external_input_boundary" for item in blockers):
        decision = MODEL_MATURATION_DECISION_EXTERNAL_INPUT_REQUIRED
        confidence = MODEL_MATURATION_CONFIDENCE_BLOCKED
        ok = False
        summary = "The next discriminating observation is external and its exact boundary is preserved."
    elif scoped_ids and not addressable and not external_signal_ids:
        decision = MODEL_MATURATION_DECISION_SCOPE_EXCLUDED
        confidence = MODEL_MATURATION_CONFIDENCE_SCOPED
        ok = False
        summary = "The task boundary explicitly excludes remaining coverage; no full-task claim is allowed."
    elif plan.iteration >= plan.max_iterations and current:
        decision = MODEL_MATURATION_DECISION_ITERATION_LIMIT
        confidence = MODEL_MATURATION_CONFIDENCE_BLOCKED
        ok = False
        summary = "The iteration budget ended while addressable gaps remained open."
    elif (plan.iteration > 0 and current and not progressed) or oscillating:
        decision = MODEL_MATURATION_DECISION_PROGRESS_STALLED
        confidence = MODEL_MATURATION_CONFIDENCE_BLOCKED
        ok = False
        summary = "The iteration did not resolve a verified gap or obtain discriminating evidence, or it repeated an earlier state."
    elif addressable or current:
        decision = MODEL_MATURATION_DECISION_UPGRADE_REQUIRED
        confidence = MODEL_MATURATION_CONFIDENCE_BLOCKED
        ok = False
        summary = "Addressable gaps require another model/evidence iteration; they cannot be scoped away."
    else:
        decision = MODEL_MATURATION_DECISION_BLOCKED
        confidence = MODEL_MATURATION_CONFIDENCE_BLOCKED
        ok = False
        summary = "The current evidence cannot establish task-local model closure."

    iteration_record = _iteration_for(
        plan,
        open_gap_fingerprints=current,
        resolved_gap_fingerprints=resolved,
        persisted_gap_fingerprints=persisted,
        introduced_gap_fingerprints=introduced,
        native_receipt_fingerprints=native_receipt_fingerprints,
        progressed=progressed,
        decision=decision,
        recommended=recommended or (MATURITY_ACTION_NO_CHANGE,),
    )

    input_fingerprint = iteration_record.input_fingerprint if iteration_record else _stable_fingerprint(plan.to_dict())
    return ModelMaturationReport(
        ok=ok,
        plan_id=plan.plan_id,
        model_id=plan.model_id,
        risk_id=plan.risk_id,
        decision=decision,
        confidence=confidence,
        recommended_actions=recommended or (MATURITY_ACTION_DOWNGRADE_CLAIM,),
        findings=tuple(findings),
        scoped_signal_ids=scoped_ids,
        summary=summary,
        task_id=plan.task_id,
        coverage_universe_id=plan.coverage_universe_id,
        coverage_universe_fingerprint=plan.coverage_universe_fingerprint,
        base_model_fingerprint=plan.base_model_fingerprint,
        candidate_model_fingerprint=plan.candidate_model_fingerprint,
        evidence_fingerprint=plan.evidence_fingerprint,
        evidence_id=f"model-maturation:{plan.plan_id}:{input_fingerprint}",
        iteration=plan.iteration,
        terminal_reason=decision if decision in MODEL_MATURATION_TERMINAL_REASONS else "",
        next_actions=recommended,
        open_gap_fingerprints=tuple(sorted(current)),
        input_fingerprint=input_fingerprint,
        progressed=progressed,
        iteration_record=iteration_record,
    )


def review_model_maturation_session(
    plans: Sequence[ModelMaturationPlan],
    *,
    session_id: str = "",
) -> ModelMaturationSession:
    """Review supplied candidate iterations until a terminal result appears."""

    reports: list[ModelMaturationReport] = []
    session_findings: list[ModelMaturationFinding] = []
    expected_task = plans[0].task_id if plans else ""
    expected_task_purpose = plans[0].task_purpose if plans else ""
    expected_plan = plans[0].plan_id if plans else ""
    expected_model = plans[0].model_id if plans else ""
    expected_coverage = plans[0].coverage_universe_fingerprint if plans else ""
    seen_states: set[str] = set()
    previous_record: ModelMaturationIteration | None = None
    for index, plan in enumerate(plans):
        if (
            plan.task_id != expected_task
            or plan.task_purpose != expected_task_purpose
            or plan.plan_id != expected_plan
            or plan.model_id != expected_model
            or plan.coverage_universe_fingerprint != expected_coverage
        ):
            session_findings.append(_plan_finding("session_identity_mismatch", "all iterations must bind the same plan, task purpose, model, and coverage universe"))
            break
        if index > 0:
            assert previous_record is not None
            if plan.iteration != plans[index - 1].iteration + 1:
                session_findings.append(_plan_finding("session_iteration_not_contiguous", "session iterations must be contiguous"))
                break
            if plan.prior_iteration_fingerprint != previous_record.fingerprint():
                session_findings.append(_plan_finding("session_predecessor_mismatch", "iteration predecessor fingerprint does not match the preceding immutable record"))
                break
            if set(plan.prior_gap_fingerprints) != set(previous_record.open_gap_fingerprints):
                session_findings.append(_plan_finding("session_prior_gap_mismatch", "iteration prior gaps do not match the preceding open-gap set"))
                break
            if plan.base_model_fingerprint != previous_record.candidate_model_fingerprint:
                session_findings.append(_plan_finding("session_model_chain_mismatch", "iteration base model does not match the preceding candidate"))
                break
        report = review_model_maturation_loop(plan)
        reports.append(report)
        if report.iteration_record is not None:
            state = _stable_fingerprint(
                {
                    "candidate": report.iteration_record.candidate_model_fingerprint,
                    "evidence": plan.evidence_fingerprint,
                    "open_gaps": list(report.iteration_record.open_gap_fingerprints),
                }
            )
            if state in seen_states and report.terminal_reason != MODEL_MATURATION_DECISION_CLOSED_FOR_TASK:
                session_findings.append(_plan_finding("session_oscillation", "session repeated an earlier candidate/evidence/open-gap state"))
                break
            seen_states.add(state)
            previous_record = report.iteration_record
        if report.terminal_reason:
            break
    task_id = next((plan.task_id for plan in plans if plan.task_id), "")
    if session_findings:
        terminal_reason = MODEL_MATURATION_DECISION_BLOCKED
    elif reports and reports[-1].terminal_reason:
        terminal_reason = reports[-1].terminal_reason
    else:
        terminal_reason = MODEL_MATURATION_DECISION_BLOCKED
        session_findings.append(_plan_finding("session_missing_terminal", "supplied iterations ended before a terminal result"))
    return ModelMaturationSession(
        session_id=session_id or (plans[0].plan_id if plans else "maturation-session"),
        task_id=task_id,
        iterations=tuple(report.iteration_record for report in reports if report.iteration_record is not None),
        terminal_reason=terminal_reason,
        findings=tuple(session_findings),
    )


__all__ = [
    "MATURITY_ACTION_ADD_CODE_BOUNDARY_OBSERVATION",
    "MATURITY_ACTION_ADD_INVARIANT",
    "MATURITY_ACTION_ADD_MODEL_OBLIGATION",
    "MATURITY_ACTION_ADD_SAME_CLASS_SCENARIO",
    "MATURITY_ACTION_ADD_STATE_FIELD",
    "MATURITY_ACTION_ADD_TRANSITION_CASE",
    "MATURITY_ACTION_DOWNGRADE_CLAIM",
    "MATURITY_ACTION_NO_CHANGE",
    "MATURITY_ACTION_REATTACH_PARENT_MODEL",
    "MATURITY_ACTION_REFRESH_EVIDENCE",
    "MATURITY_ACTION_SPLIT_CHILD_MODEL",
    "MODEL_MATURATION_ACTIONS_BY_SIGNAL",
    "MODEL_MATURATION_CONFIDENCE_BLOCKED",
    "MODEL_MATURATION_CONFIDENCE_FULL",
    "MODEL_MATURATION_CONFIDENCE_SCOPED",
    "MODEL_MATURATION_DECISION_CLOSED_FOR_TASK",
    "MODEL_MATURATION_DECISION_BLOCKED",
    "MODEL_MATURATION_DECISION_EXTERNAL_INPUT_REQUIRED",
    "MODEL_MATURATION_DECISION_ITERATION_LIMIT",
    "MODEL_MATURATION_DECISION_PROGRESS_STALLED",
    "MODEL_MATURATION_DECISION_UPGRADE_REQUIRED",
    "MODEL_MATURATION_DECISION_SCOPE_EXCLUDED",
    "MODEL_MATURATION_RESOLUTION_CLASSES",
    "MODEL_MATURATION_RESOLUTION_EVIDENCE_ACQUISITION",
    "MODEL_MATURATION_RESOLUTION_EXTERNAL_INPUT_REQUIRED",
    "MODEL_MATURATION_RESOLUTION_MODEL_EDIT",
    "MODEL_MATURATION_RESOLUTION_SCOPE_EXCLUDED",
    "MODEL_MATURATION_PLAN_SCHEMA_VERSION",
    "MODEL_MATURATION_INTAKE_SCHEMA_VERSION",
    "MODEL_MATURATION_RECEIPT_STATUS_PASS",
    "MODEL_MATURATION_TERMINAL_REASONS",
    "MODEL_MATURATION_SIGNAL_BOUNDARY_MISSING",
    "MODEL_MATURATION_SIGNAL_CHILD_BOUNDARY_CHANGED",
    "MODEL_MATURATION_SIGNAL_CHILD_REATTACHMENT_MISSING",
    "MODEL_MATURATION_SIGNAL_CODE_BOUNDARY_MISMATCH",
    "MODEL_MATURATION_SIGNAL_DUPLICATE_PRIMARY_EDGE_PATH",
    "MODEL_MATURATION_SIGNAL_INPUT_BRANCH_MISSING",
    "MODEL_MATURATION_SIGNAL_INVARIANT_TOO_WEAK",
    "MODEL_MATURATION_SIGNAL_MISSING_CODE_BOUNDARY_OBSERVATION",
    "MODEL_MATURATION_SIGNAL_MISSING_MODEL_OBLIGATION",
    "MODEL_MATURATION_SIGNAL_OVERSIZED_MODEL",
    "MODEL_MATURATION_SIGNAL_PROGRESS_ONLY_EVIDENCE",
    "MODEL_MATURATION_SIGNAL_SAME_CLASS_MISSING",
    "MODEL_MATURATION_SIGNAL_STALE_EVIDENCE",
    "MODEL_MATURATION_SIGNAL_STATE_TOO_COARSE",
    "MODEL_MATURATION_SIGNAL_TYPES",
    "ModelMaturationCoverageContribution",
    "ModelMaturationEvidenceRef",
    "ModelMaturationFinding",
    "ModelMaturationGapResolutionReceipt",
    "ModelMaturationIntake",
    "ModelMaturationIteration",
    "ModelMaturationPlan",
    "ModelMaturationReport",
    "ModelMaturationSession",
    "ModelMaturationSignal",
    "coerce_model_maturation_evidence_ref",
    "compile_model_maturation_plan",
    "review_model_maturation_session",
    "review_model_maturation_loop",
]
