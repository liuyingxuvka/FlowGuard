from __future__ import annotations

from flowguard.model_miss_diagnostics import (
    ATOM_ROLE_CODE_TEST_SURFACE,
    ATOM_ROLE_FAILURE_BOUNDARY,
    ATOM_ROLE_MODEL_EXPECTATION,
    ATOM_ROLE_OBSERVATION,
    ATOM_ROLE_POSITIVE_OBLIGATION,
    DiagnosticAtom,
    DisagreementBinding,
    RepairCandidate,
    diagnose_false_negative_backpropagation,
)
from flowguard.plan_intake import (
    FALSE_NEGATIVE_DECISION_BLOCKED,
    FalseNegativeBackpropagationReport,
    FalseNegativeFinding,
)


def _report() -> FalseNegativeBackpropagationReport:
    return FalseNegativeBackpropagationReport(
        ok=False,
        plan_id="plan:model-miss",
        decision=FALSE_NEGATIVE_DECISION_BLOCKED,
        confidence="blocked",
        findings=(
            FalseNegativeFinding(
                "missing_would_have_failed_if",
                "condition missing",
                case_id="case:one",
            ),
        ),
    )


def _conflict_atoms() -> tuple[DiagnosticAtom, ...]:
    return (
        DiagnosticAtom("noise", ATOM_ROLE_OBSERVATION, "observation:noise"),
        DiagnosticAtom(
            "missing-input",
            ATOM_ROLE_MODEL_EXPECTATION,
            "model:expected-input",
        ),
        DiagnosticAtom(
            "weak-oracle",
            ATOM_ROLE_OBSERVATION,
            "observation:accepted-invalid",
        ),
        DiagnosticAtom(
            "handler",
            ATOM_ROLE_CODE_TEST_SURFACE,
            "code:public-handler",
        ),
        DiagnosticAtom(
            "boundary",
            ATOM_ROLE_FAILURE_BOUNDARY,
            "boundary:invalid-input-accepted",
        ),
    )


def _positive_atoms() -> tuple[DiagnosticAtom, ...]:
    return (
        DiagnosticAtom(
            "unneeded",
            ATOM_ROLE_POSITIVE_OBLIGATION,
            "obligation:unneeded",
        ),
        DiagnosticAtom(
            "known-good",
            ATOM_ROLE_POSITIVE_OBLIGATION,
            "obligation:known-good",
        ),
    )


def _binding() -> DisagreementBinding:
    return DisagreementBinding(
        binding_id="disagreement:invalid-input",
        observation_atom_id="weak-oracle",
        model_expectation_atom_id="missing-input",
        code_test_surface_atom_ids=("handler",),
        failure_boundary_atom_id="boundary",
    )


def test_projection_extracts_deletion_minimal_conflict_and_positive_witness() -> None:
    projection = diagnose_false_negative_backpropagation(
        _report(),
        conflict_atoms=_conflict_atoms(),
        conflict_oracle=lambda ids: {
            "missing-input",
            "weak-oracle",
        }
        <= set(ids),
        positive_atoms=_positive_atoms(),
        positive_oracle=lambda ids: "known-good" in ids,
        disagreement_bindings=(_binding(),),
    )
    assert projection.status == "blocked"
    assert projection.diagnostic_status == "complete"
    assert projection.conflict is not None
    assert projection.conflict.evidence_ids == (
        "missing-input",
        "weak-oracle",
    )
    assert projection.positive_witness is not None
    assert projection.positive_witness.evidence_ids == ("known-good",)
    assert projection.closure_licensed is False
    assert projection.owner_decision == _report().decision
    assert "parent_review_blocked" in projection.blocker_codes


def test_missing_positive_witness_is_visible_blocker() -> None:
    projection = diagnose_false_negative_backpropagation(
        _report(),
        conflict_atoms=_conflict_atoms(),
        conflict_oracle=lambda ids: {
            "missing-input",
            "weak-oracle",
        }
        <= set(ids),
        positive_atoms=(
            DiagnosticAtom(
                "candidate",
                ATOM_ROLE_POSITIVE_OBLIGATION,
                "obligation:candidate",
            ),
        ),
        positive_oracle=lambda _ids: False,
        disagreement_bindings=(_binding(),),
    )
    assert projection.status == "blocked"
    assert "missing_positive_non_vacuity_witness" in projection.blocker_codes


def test_green_owner_report_does_not_require_conflict() -> None:
    report = FalseNegativeBackpropagationReport(
        ok=True,
        plan_id="plan:green",
        decision="false_negative_backpropagation_full_confidence",
        confidence="full",
    )
    projection = diagnose_false_negative_backpropagation(
        report,
        conflict_atoms=(),
        conflict_oracle=lambda _ids: False,
        positive_atoms=(
            DiagnosticAtom(
                "known-good",
                ATOM_ROLE_POSITIVE_OBLIGATION,
                "obligation:known-good",
            ),
        ),
        positive_oracle=lambda ids: "known-good" in ids,
    )
    assert projection.status == "complete"
    assert projection.conflict is None


def test_budget_exhaustion_is_bounded_incomplete_not_subset_minimal() -> None:
    projection = diagnose_false_negative_backpropagation(
        _report(),
        conflict_atoms=_conflict_atoms(),
        conflict_oracle=lambda ids: {
            "missing-input",
            "weak-oracle",
        }
        <= set(ids),
        positive_atoms=_positive_atoms(),
        positive_oracle=lambda ids: "known-good" in ids,
        disagreement_bindings=(_binding(),),
        max_conflict_oracle_calls=1,
    )
    assert projection.diagnostic_status == "bounded_incomplete"
    assert projection.conflict is not None
    assert projection.conflict.status == "bounded_incomplete"
    assert projection.conflict.deletion_minimal is False
    assert "conflict_budget_exhausted" in projection.blocker_codes


def test_repair_that_removes_obligation_is_rejected_as_vacuous() -> None:
    projection = diagnose_false_negative_backpropagation(
        _report(),
        conflict_atoms=_conflict_atoms(),
        conflict_oracle=lambda ids: {
            "missing-input",
            "weak-oracle",
        }
        <= set(ids),
        positive_atoms=_positive_atoms(),
        positive_oracle=lambda ids: "known-good" in ids,
        disagreement_bindings=(_binding(),),
        repair_candidate=RepairCandidate(
            candidate_id="repair:vacuous",
            preserved_positive_obligation_ids=("obligation:known-good",),
            rejects_original_miss=True,
            rejection_reason_id="reason:deleted-contract",
            removes_affected_obligation=True,
        ),
    )
    assert projection.repair_assessment is not None
    assert projection.repair_assessment.status == "rejected_vacuous"
    assert "repair_removes_affected_obligation" in projection.blocker_codes


def test_non_vacuous_repair_is_routed_to_model_test_alignment() -> None:
    report = FalseNegativeBackpropagationReport(
        ok=True,
        plan_id="plan:repaired",
        decision="false_negative_backpropagation_full_confidence",
        confidence="full",
    )
    projection = diagnose_false_negative_backpropagation(
        report,
        conflict_atoms=(),
        conflict_oracle=lambda _ids: False,
        positive_atoms=_positive_atoms(),
        positive_oracle=lambda ids: "known-good" in ids,
        repair_candidate=RepairCandidate(
            candidate_id="repair:bounded",
            preserved_positive_obligation_ids=("obligation:known-good",),
            changed_contract_ids=("contract:input-rejection",),
            new_negative_evidence_ids=("evidence:original-miss-rejected",),
            rejects_original_miss=True,
            rejection_reason_id="reason:required-input-missing",
        ),
    )
    assert projection.status == "complete"
    assert projection.repair_assessment is not None
    assert projection.repair_assessment.status == "accepted_for_validation"
    assert (
        projection.repair_assessment.required_next_route
        == "model_test_alignment"
    )
