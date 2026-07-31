"""Run the bug-repair/model-miss review template."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from model import run_checks
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
)


def _check_diagnostic_projection() -> bool:
    report = FalseNegativeBackpropagationReport(
        ok=False,
        plan_id="plan:model-miss-diagnostic",
        decision=FALSE_NEGATIVE_DECISION_BLOCKED,
        confidence="blocked",
    )
    conflict_atoms = (
        DiagnosticAtom("irrelevant", ATOM_ROLE_OBSERVATION, "obs:noise"),
        DiagnosticAtom("model", ATOM_ROLE_MODEL_EXPECTATION, "model:one"),
        DiagnosticAtom("observation", ATOM_ROLE_OBSERVATION, "obs:one"),
        DiagnosticAtom("code", ATOM_ROLE_CODE_TEST_SURFACE, "code:one"),
        DiagnosticAtom("boundary", ATOM_ROLE_FAILURE_BOUNDARY, "boundary:one"),
    )
    positive_atoms = (
        DiagnosticAtom(
            "preserved-positive",
            ATOM_ROLE_POSITIVE_OBLIGATION,
            "obligation:preserved-positive",
        ),
    )
    disagreement_bindings = (
        DisagreementBinding(
            binding_id="disagreement:one",
            observation_atom_id="observation",
            model_expectation_atom_id="model",
            code_test_surface_atom_ids=("code",),
            failure_boundary_atom_id="boundary",
        ),
    )
    common = {
        "conflict_atoms": conflict_atoms,
        "conflict_oracle": lambda ids: {"model", "observation"} <= set(ids),
        "positive_atoms": positive_atoms,
        "positive_oracle": lambda ids: "preserved-positive" in ids,
        "disagreement_bindings": disagreement_bindings,
    }
    projection = diagnose_false_negative_backpropagation(report, **common)
    bounded = diagnose_false_negative_backpropagation(
        report,
        **common,
        max_conflict_oracle_calls=1,
    )
    vacuous = diagnose_false_negative_backpropagation(
        report,
        **common,
        repair_candidate=RepairCandidate(
            candidate_id="repair:vacuous",
            preserved_positive_obligation_ids=(
                "obligation:preserved-positive",
            ),
            rejects_original_miss=True,
            rejection_reason_id="reason:deleted-obligation",
            removes_affected_obligation=True,
        ),
    )
    return (
        projection.status == "blocked"
        and projection.diagnostic_status == "complete"
        and projection.owner_decision == report.decision
        and projection.closure_licensed is False
        and projection.conflict is not None
        and projection.conflict.deletion_minimal
        and projection.positive_witness is not None
        and projection.positive_witness.deletion_minimal
        and bounded.diagnostic_status == "bounded_incomplete"
        and bounded.conflict is not None
        and bounded.conflict.deletion_minimal is False
        and vacuous.repair_assessment is not None
        and vacuous.repair_assessment.status == "rejected_vacuous"
    )


def main() -> int:
    correct, broken = run_checks()
    diagnostic_ok = _check_diagnostic_projection()
    print(f"{correct.scenario_name}: {correct.status.upper()}")
    for item in correct.evidence:
        print(f"  - {item}")
    print()
    print(broken.format_text(max_counterexamples=2))
    print()
    print(
        "model-miss diagnostic projection: "
        + ("PASS" if diagnostic_ok else "FAIL")
    )
    return 0 if correct.ok and broken.ok and diagnostic_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
