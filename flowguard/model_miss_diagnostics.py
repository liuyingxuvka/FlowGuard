"""Subordinate diagnostic evidence for the existing Model-Miss Review owner."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Sequence

from .plan_intake import FalseNegativeBackpropagationReport


EvidenceOracle = Callable[[tuple[str, ...]], bool]

DIAGNOSTIC_ALGORITHM_VERSION = "deletion-minimal.v1"
ATOM_ROLE_OBSERVATION = "observation"
ATOM_ROLE_MODEL_EXPECTATION = "model_expectation"
ATOM_ROLE_CODE_TEST_SURFACE = "code_test_surface"
ATOM_ROLE_FAILURE_BOUNDARY = "failure_boundary"
ATOM_ROLE_POSITIVE_OBLIGATION = "positive_obligation"
DIAGNOSTIC_ATOM_ROLES = (
    ATOM_ROLE_CODE_TEST_SURFACE,
    ATOM_ROLE_FAILURE_BOUNDARY,
    ATOM_ROLE_MODEL_EXPECTATION,
    ATOM_ROLE_OBSERVATION,
    ATOM_ROLE_POSITIVE_OBLIGATION,
)
REQUIRED_CONFLICT_ROLES = (
    ATOM_ROLE_OBSERVATION,
    ATOM_ROLE_MODEL_EXPECTATION,
    ATOM_ROLE_CODE_TEST_SURFACE,
    ATOM_ROLE_FAILURE_BOUNDARY,
)


@dataclass(frozen=True)
class DiagnosticAtom:
    atom_id: str
    role: str
    binding_id: str

    def __post_init__(self) -> None:
        if not self.atom_id.strip():
            raise ValueError("diagnostic atom requires atom_id")
        if self.role not in DIAGNOSTIC_ATOM_ROLES:
            raise ValueError(f"unsupported diagnostic atom role: {self.role}")
        if not self.binding_id.strip():
            raise ValueError("diagnostic atom requires exact binding_id")

    def to_dict(self) -> dict[str, str]:
        return {
            "atom_id": self.atom_id,
            "role": self.role,
            "binding_id": self.binding_id,
        }


@dataclass(frozen=True)
class DisagreementBinding:
    binding_id: str
    observation_atom_id: str
    model_expectation_atom_id: str
    code_test_surface_atom_ids: tuple[str, ...]
    failure_boundary_atom_id: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "binding_id": self.binding_id,
            "observation_atom_id": self.observation_atom_id,
            "model_expectation_atom_id": self.model_expectation_atom_id,
            "code_test_surface_atom_ids": list(self.code_test_surface_atom_ids),
            "failure_boundary_atom_id": self.failure_boundary_atom_id,
        }


@dataclass(frozen=True)
class NecessityWitness:
    atom_id: str
    necessary: bool

    def to_dict(self) -> dict[str, Any]:
        return {"atom_id": self.atom_id, "necessary": self.necessary}


@dataclass(frozen=True)
class SubsetMinimalEvidence:
    atoms: tuple[DiagnosticAtom, ...]
    necessity_witnesses: tuple[NecessityWitness, ...]
    status: str
    deletion_minimal: bool
    oracle_calls: int
    max_oracle_calls: int | None
    input_order: tuple[str, ...]
    algorithm_version: str = DIAGNOSTIC_ALGORITHM_VERSION

    @property
    def evidence_ids(self) -> tuple[str, ...]:
        return tuple(atom.atom_id for atom in self.atoms)

    def to_dict(self) -> dict[str, Any]:
        return {
            "atoms": [atom.to_dict() for atom in self.atoms],
            "evidence_ids": list(self.evidence_ids),
            "necessity_witnesses": [
                witness.to_dict() for witness in self.necessity_witnesses
            ],
            "status": self.status,
            "deletion_minimal": self.deletion_minimal,
            "oracle_calls": self.oracle_calls,
            "max_oracle_calls": self.max_oracle_calls,
            "input_order": list(self.input_order),
            "algorithm_version": self.algorithm_version,
        }


@dataclass(frozen=True)
class RepairCandidate:
    candidate_id: str
    preserved_positive_obligation_ids: tuple[str, ...]
    changed_assumption_ids: tuple[str, ...] = ()
    changed_transition_ids: tuple[str, ...] = ()
    changed_contract_ids: tuple[str, ...] = ()
    new_negative_evidence_ids: tuple[str, ...] = ()
    rejects_original_miss: bool = False
    rejection_reason_id: str = ""
    removes_affected_obligation: bool = False


@dataclass(frozen=True)
class RepairAssessment:
    candidate_id: str
    status: str
    blocker_codes: tuple[str, ...]
    preserved_positive_obligation_ids: tuple[str, ...]
    required_next_route: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "status": self.status,
            "blocker_codes": list(self.blocker_codes),
            "preserved_positive_obligation_ids": list(
                self.preserved_positive_obligation_ids
            ),
            "required_next_route": self.required_next_route,
        }


@dataclass(frozen=True)
class ModelMissDiagnosticProjection:
    owner_plan_id: str
    owner_decision: str
    owner_status: str
    status: str
    diagnostic_status: str
    conflict: SubsetMinimalEvidence | None
    positive_witness: SubsetMinimalEvidence | None
    disagreement_bindings: tuple[DisagreementBinding, ...]
    repair_assessment: RepairAssessment | None
    blocker_codes: tuple[str, ...]
    closure_licensed: bool = False
    claim_boundary: str = (
        "This is a read-only diagnostic projection subordinate to the existing "
        "FalseNegativeBackpropagation report. It neither changes that report's "
        "decision nor creates a second Model-Miss Review or closure owner."
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifact_kind": "flowguard.model_miss_diagnostic_projection.v1",
            "owner_plan_id": self.owner_plan_id,
            "owner_decision": self.owner_decision,
            "owner_status": self.owner_status,
            "status": self.status,
            "diagnostic_status": self.diagnostic_status,
            "conflict": self.conflict.to_dict() if self.conflict else None,
            "positive_witness": (
                self.positive_witness.to_dict()
                if self.positive_witness
                else None
            ),
            "disagreement_bindings": [
                binding.to_dict() for binding in self.disagreement_bindings
            ],
            "repair_assessment": (
                self.repair_assessment.to_dict()
                if self.repair_assessment
                else None
            ),
            "blocker_codes": list(self.blocker_codes),
            "closure_licensed": self.closure_licensed,
            "claim_boundary": self.claim_boundary,
        }


def _deletion_minimal(
    atoms: Sequence[DiagnosticAtom],
    *,
    oracle: EvidenceOracle,
    max_oracle_calls: int | None,
) -> SubsetMinimalEvidence | None:
    atom_by_id = {atom.atom_id: atom for atom in atoms}
    input_order = tuple(sorted(atom_by_id))
    candidate = list(input_order)
    calls = 0

    def evaluate(atom_ids: tuple[str, ...]) -> bool | None:
        nonlocal calls
        if max_oracle_calls is not None and calls >= max_oracle_calls:
            return None
        calls += 1
        return bool(oracle(atom_ids))

    if not candidate:
        return None
    initial = evaluate(tuple(candidate))
    if initial is None:
        return SubsetMinimalEvidence(
            atoms=tuple(atom_by_id[item] for item in candidate),
            necessity_witnesses=(),
            status="bounded_incomplete",
            deletion_minimal=False,
            oracle_calls=calls,
            max_oracle_calls=max_oracle_calls,
            input_order=input_order,
        )
    if not initial:
        return None
    for evidence_id in tuple(candidate):
        reduced = tuple(item for item in candidate if item != evidence_id)
        outcome = evaluate(reduced)
        if outcome is None:
            return SubsetMinimalEvidence(
                atoms=tuple(atom_by_id[item] for item in candidate),
                necessity_witnesses=(),
                status="bounded_incomplete",
                deletion_minimal=False,
                oracle_calls=calls,
                max_oracle_calls=max_oracle_calls,
                input_order=input_order,
            )
        if outcome:
            candidate = list(reduced)
    minimal = tuple(candidate)
    witnesses: list[NecessityWitness] = []
    for evidence_id in minimal:
        reduced = tuple(item for item in minimal if item != evidence_id)
        outcome = evaluate(reduced)
        if outcome is None:
            return SubsetMinimalEvidence(
                atoms=tuple(atom_by_id[item] for item in minimal),
                necessity_witnesses=tuple(witnesses),
                status="bounded_incomplete",
                deletion_minimal=False,
                oracle_calls=calls,
                max_oracle_calls=max_oracle_calls,
                input_order=input_order,
            )
        witnesses.append(NecessityWitness(evidence_id, not outcome))
    return SubsetMinimalEvidence(
        atoms=tuple(atom_by_id[item] for item in minimal),
        necessity_witnesses=tuple(witnesses),
        status="complete",
        deletion_minimal=all(item.necessary for item in witnesses),
        oracle_calls=calls,
        max_oracle_calls=max_oracle_calls,
        input_order=input_order,
    )


def _assess_repair_candidate(
    candidate: RepairCandidate | None,
    positive_witness: SubsetMinimalEvidence | None,
) -> RepairAssessment | None:
    if candidate is None:
        return None
    blockers: list[str] = []
    if not candidate.preserved_positive_obligation_ids:
        blockers.append("repair_missing_preserved_positive_obligation")
    if candidate.removes_affected_obligation:
        blockers.append("repair_removes_affected_obligation")
    if not candidate.rejects_original_miss:
        blockers.append("repair_does_not_reject_original_miss")
    if not candidate.rejection_reason_id.strip():
        blockers.append("repair_missing_intended_rejection_reason")
    witnessed_bindings = {
        atom.binding_id
        for atom in positive_witness.atoms
        if positive_witness is not None
    } if positive_witness is not None else set()
    missing_preserved = sorted(
        set(candidate.preserved_positive_obligation_ids) - witnessed_bindings
    )
    if missing_preserved:
        blockers.append("repair_positive_obligation_not_witnessed")
    return RepairAssessment(
        candidate_id=candidate.candidate_id,
        status="accepted_for_validation" if not blockers else "rejected_vacuous",
        blocker_codes=tuple(blockers),
        preserved_positive_obligation_ids=tuple(
            sorted(set(candidate.preserved_positive_obligation_ids))
        ),
        required_next_route=(
            "model_test_alignment" if not blockers else "model_miss_review"
        ),
    )


def _validate_disagreement_bindings(
    atoms: Sequence[DiagnosticAtom],
    bindings: Sequence[DisagreementBinding],
) -> tuple[str, ...]:
    atom_by_id = {atom.atom_id: atom for atom in atoms}
    blockers: list[str] = []
    if atoms and not bindings:
        blockers.append("missing_disagreement_binding")
    for binding in bindings:
        expected = (
            (binding.observation_atom_id, ATOM_ROLE_OBSERVATION),
            (binding.model_expectation_atom_id, ATOM_ROLE_MODEL_EXPECTATION),
            (binding.failure_boundary_atom_id, ATOM_ROLE_FAILURE_BOUNDARY),
            *(
                (atom_id, ATOM_ROLE_CODE_TEST_SURFACE)
                for atom_id in binding.code_test_surface_atom_ids
            ),
        )
        for atom_id, role in expected:
            atom = atom_by_id.get(atom_id)
            if atom is None:
                blockers.append("disagreement_binding_unknown_atom")
            elif atom.role != role:
                blockers.append("disagreement_binding_role_mismatch")
        if not binding.code_test_surface_atom_ids:
            blockers.append("disagreement_binding_missing_code_test_surface")
    return tuple(sorted(set(blockers)))


def diagnose_false_negative_backpropagation(
    report: FalseNegativeBackpropagationReport,
    *,
    conflict_atoms: Sequence[DiagnosticAtom],
    conflict_oracle: EvidenceOracle,
    positive_atoms: Sequence[DiagnosticAtom],
    positive_oracle: EvidenceOracle,
    disagreement_bindings: Sequence[DisagreementBinding] = (),
    repair_candidate: RepairCandidate | None = None,
    max_conflict_oracle_calls: int | None = None,
    max_positive_oracle_calls: int | None = None,
    parent_observed_evidence_current: bool = True,
) -> ModelMissDiagnosticProjection:
    """Explain one existing owner report with conflict and non-vacuity proof."""

    conflict = _deletion_minimal(
        conflict_atoms,
        oracle=conflict_oracle,
        max_oracle_calls=max_conflict_oracle_calls,
    )
    positive = _deletion_minimal(
        positive_atoms,
        oracle=positive_oracle,
        max_oracle_calls=max_positive_oracle_calls,
    )
    blockers: list[str] = []
    diagnostic_blockers: list[str] = []
    if not report.ok:
        blockers.append("parent_review_blocked")
    if not parent_observed_evidence_current:
        blockers.append("missing_current_observed_evidence")
        diagnostic_blockers.append("missing_current_observed_evidence")
    conflict_roles = {atom.role for atom in conflict_atoms}
    if not report.ok:
        for role in REQUIRED_CONFLICT_ROLES:
            if role not in conflict_roles:
                code = f"missing_conflict_role:{role}"
                blockers.append(code)
                diagnostic_blockers.append(code)
    binding_blockers = _validate_disagreement_bindings(
        conflict_atoms,
        disagreement_bindings,
    )
    blockers.extend(binding_blockers)
    diagnostic_blockers.extend(binding_blockers)
    if not report.ok and conflict is None:
        blockers.append("missing_subset_minimal_conflict")
        diagnostic_blockers.append("missing_subset_minimal_conflict")
    if positive is None:
        blockers.append("missing_positive_non_vacuity_witness")
        diagnostic_blockers.append("missing_positive_non_vacuity_witness")
    if conflict is not None and conflict.status == "bounded_incomplete":
        blockers.append("conflict_budget_exhausted")
        diagnostic_blockers.append("conflict_budget_exhausted")
    if positive is not None and positive.status == "bounded_incomplete":
        blockers.append("positive_budget_exhausted")
        diagnostic_blockers.append("positive_budget_exhausted")
    if conflict is not None and not conflict.deletion_minimal:
        blockers.append("conflict_not_deletion_minimal")
        diagnostic_blockers.append("conflict_not_deletion_minimal")
    if positive is not None and not positive.deletion_minimal:
        blockers.append("positive_witness_not_deletion_minimal")
        diagnostic_blockers.append("positive_witness_not_deletion_minimal")
    repair_assessment = _assess_repair_candidate(
        repair_candidate,
        positive,
    )
    if repair_assessment is not None and repair_assessment.blocker_codes:
        blockers.extend(repair_assessment.blocker_codes)
        diagnostic_blockers.extend(repair_assessment.blocker_codes)
    bounded = any(
        item is not None and item.status == "bounded_incomplete"
        for item in (conflict, positive)
    )
    diagnostic_status = (
        "bounded_incomplete"
        if bounded
        else ("blocked" if diagnostic_blockers else "complete")
    )
    status = "complete" if not blockers else "blocked"
    return ModelMissDiagnosticProjection(
        owner_plan_id=report.plan_id,
        owner_decision=report.decision,
        owner_status="pass" if report.ok else "blocked",
        status=status,
        diagnostic_status=diagnostic_status,
        conflict=conflict,
        positive_witness=positive,
        disagreement_bindings=tuple(disagreement_bindings),
        repair_assessment=repair_assessment,
        blocker_codes=tuple(sorted(set(blockers))),
        closure_licensed=False,
    )


__all__ = [
    "ATOM_ROLE_CODE_TEST_SURFACE",
    "ATOM_ROLE_FAILURE_BOUNDARY",
    "ATOM_ROLE_MODEL_EXPECTATION",
    "ATOM_ROLE_OBSERVATION",
    "ATOM_ROLE_POSITIVE_OBLIGATION",
    "DIAGNOSTIC_ALGORITHM_VERSION",
    "DIAGNOSTIC_ATOM_ROLES",
    "DiagnosticAtom",
    "DisagreementBinding",
    "EvidenceOracle",
    "ModelMissDiagnosticProjection",
    "NecessityWitness",
    "RepairAssessment",
    "RepairCandidate",
    "REQUIRED_CONFLICT_ROLES",
    "SubsetMinimalEvidence",
    "diagnose_false_negative_backpropagation",
]
