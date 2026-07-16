from __future__ import annotations

import dataclasses
from pathlib import Path
import unittest

import flowguard.development_process_strategy as strategy
from flowguard.development_process_strategy import (
    ProcessOptimizationCandidate,
    ProcessOptimizationContract,
    ProcessOptimizationDecision,
    ProcessOptimizationReport,
    ProcessRepairGroup,
    review_process_optimization,
)


def _contract() -> ProcessOptimizationContract:
    return ProcessOptimizationContract(
        "contract:repair",
        terminal_outcome_ids=("outcome:green",),
        required_obligation_ids=("obligation:a", "obligation:b"),
        required_evidence_ids=("evidence:required",),
        safety_constraint_ids=("safety:no-destructive-probe",),
        protected_side_effect_ids=("side-effect:workspace",),
        dependency_authority_ids=("dependency:owner",),
        execution_owner_ids=("execution:owner",),
        revision="r1",
    )


def _candidate(
    candidate_id: str = "candidate:boundary-first",
    **changes: object,
) -> ProcessOptimizationCandidate:
    values: dict[str, object] = {
        "candidate_id": candidate_id,
        "contract_id": "contract:repair",
        "terminal_outcome_ids": ("outcome:green",),
        "covered_obligation_ids": ("obligation:a", "obligation:b"),
        "evidence_ids": ("evidence:required",),
        "safety_constraint_ids": ("safety:no-destructive-probe",),
        "protected_side_effect_ids": ("side-effect:workspace",),
        "dependency_authority_ids": ("dependency:owner",),
        "execution_owner_ids": ("execution:owner",),
        "step_ids": ("diagnose", "repair"),
        "validation_requirement_ids": ("revalidate",),
        "dependency_edges": (("diagnose", "repair"), ("repair", "revalidate")),
        "diagnostic_boundary": "budgeted",
        "execution_mode": "sequential",
        "comparison_basis": "qualitative",
        "comparison_evidence_ids": ("evidence:comparison",),
    }
    values.update(changes)
    return ProcessOptimizationCandidate(**values)


def _decision(
    *,
    candidates: tuple[ProcessOptimizationCandidate, ...] | None = None,
    repair_groups: tuple[ProcessRepairGroup, ...] = (),
    reasons: tuple[str, ...] = ("material_rework_risk",),
    selected: str = "candidate:boundary-first",
    current_evidence_ids: tuple[str, ...] = (
        "evidence:required",
        "evidence:comparison",
        "evidence:material",
    ),
) -> ProcessOptimizationDecision:
    return ProcessOptimizationDecision(
        "decision:repair",
        _contract(),
        activation_reasons=reasons,
        candidates=candidates if candidates is not None else (_candidate(),),
        repair_groups=repair_groups,
        selected_candidate_id=selected,
        input_revision="input:r1",
        current_evidence_ids=current_evidence_ids,
        material_evidence_ids=("evidence:material",),
        selection_rationale="collect related evidence before one root-cause repair",
    )


class DevelopmentProcessStrategyTests(unittest.TestCase):
    def test_ordinary_single_route_has_no_optimizer_ceremony(self) -> None:
        report = review_process_optimization(
            ProcessOptimizationDecision("decision:ordinary", _contract())
        )
        self.assertTrue(report.ok)
        self.assertEqual(report.status, "not_needed")
        self.assertEqual(report.eligible_candidate_ids, ())
        self.assertEqual(report.required_revalidation_ids, ())

    def test_inactive_route_rejects_unnecessary_candidates(self) -> None:
        report = review_process_optimization(
            ProcessOptimizationDecision(
                "decision:ordinary",
                _contract(),
                candidates=(_candidate(),),
            )
        )
        self.assertFalse(report.ok)
        self.assertIn("inactive_optimizer_state_present", report.finding_codes)

    def test_valid_qualitative_selection_has_a_bounded_claim(self) -> None:
        report = review_process_optimization(_decision())
        self.assertTrue(report.ok)
        self.assertEqual(report.status, "selected")
        self.assertIn("current qualitative evidence", report.claim_boundary)
        self.assertIn("no unrestricted global optimum", report.claim_boundary)

    def test_measured_selection_still_does_not_claim_global_optimality(self) -> None:
        report = review_process_optimization(
            _decision(candidates=(_candidate(comparison_basis="measured"),))
        )
        self.assertTrue(report.ok)
        self.assertIn("current measured evidence", report.claim_boundary)
        self.assertIn("no unrestricted global optimum", report.claim_boundary)

    def test_non_equivalent_candidate_is_rejected_before_comparison(self) -> None:
        candidate = _candidate(covered_obligation_ids=("obligation:a",))
        report = review_process_optimization(_decision(candidates=(candidate,)))
        self.assertFalse(report.ok)
        self.assertIn("selected_candidate_ineligible", report.finding_codes)
        self.assertTrue(
            any(code.endswith("obligation_boundary_mismatch") for code in report.finding_codes)
        )

    def test_dependency_cycle_blocks_candidate(self) -> None:
        candidate = _candidate(
            dependency_edges=(("diagnose", "repair"), ("repair", "diagnose"))
        )
        report = review_process_optimization(_decision(candidates=(candidate,)))
        self.assertTrue(any(code.endswith("dependency_cycle") for code in report.finding_codes))

    def test_safe_parallel_requires_four_isolation_evidence_boundaries(self) -> None:
        candidate = _candidate(execution_mode="safe_parallel")
        report = review_process_optimization(_decision(candidates=(candidate,)))
        self.assertTrue(
            any(
                code.endswith("parallel_isolation_evidence_missing")
                for code in report.finding_codes
            )
        )

    def test_safe_parallel_is_eligible_with_current_isolation_evidence(self) -> None:
        isolation = (
            "evidence:dependency-isolation",
            "evidence:state-isolation",
            "evidence:side-effect-isolation",
            "evidence:owner-isolation",
        )
        candidate = _candidate(
            execution_mode="safe_parallel",
            dependency_isolation_evidence_ids=(isolation[0],),
            state_isolation_evidence_ids=(isolation[1],),
            side_effect_isolation_evidence_ids=(isolation[2],),
            execution_owner_isolation_evidence_ids=(isolation[3],),
        )
        report = review_process_optimization(
            _decision(
                candidates=(candidate,),
                current_evidence_ids=(
                    "evidence:required",
                    "evidence:comparison",
                    "evidence:material",
                )
                + isolation,
            )
        )
        self.assertTrue(report.ok)

    def test_all_evidence_references_must_resolve_to_current_evidence(self) -> None:
        report = review_process_optimization(
            _decision(current_evidence_ids=("evidence:required", "evidence:material"))
        )
        self.assertFalse(report.ok)
        self.assertIn(
            "current_evidence_reference_missing:candidate:candidate:boundary-first:comparison",
            report.finding_codes,
        )

    def test_correlated_findings_can_share_one_complete_repair(self) -> None:
        group = ProcessRepairGroup(
            "repair:shared-parser",
            finding_ids=("finding:a", "finding:b"),
            relation_evidence_ids=("evidence:relation",),
            root_cause_claim="both failures cross the same parser boundary",
            disproof_check_ids=("check:disprove-parser",),
            affected_obligation_ids=("obligation:a", "obligation:b"),
            owner_evidence_ids=("evidence:owner",),
            repair_action_ids=("repair",),
            required_revalidation_ids=("evidence:revalidation",),
            current_revalidation_ids=("evidence:revalidation",),
            status="complete",
        )
        report = review_process_optimization(
            _decision(
                repair_groups=(group,),
                current_evidence_ids=(
                    "evidence:required",
                    "evidence:comparison",
                    "evidence:material",
                    "evidence:relation",
                    "evidence:owner",
                    "evidence:revalidation",
                ),
            )
        )
        self.assertTrue(report.ok)
        self.assertEqual(report.required_revalidation_ids, ("evidence:revalidation",))

    def test_unrelated_findings_are_not_grouped_by_wording(self) -> None:
        group = ProcessRepairGroup(
            "repair:unsupported",
            finding_ids=("finding:a", "finding:b"),
            root_cause_claim="same error wording",
            disproof_check_ids=("check:disprove",),
            affected_obligation_ids=("obligation:a",),
            owner_evidence_ids=("evidence:owner",),
            repair_action_ids=("repair",),
            required_revalidation_ids=("evidence:revalidation",),
        )
        report = review_process_optimization(_decision(repair_groups=(group,)))
        self.assertTrue(
            any(code.endswith("relation_evidence_missing") for code in report.finding_codes)
        )

    def test_completed_repair_requires_every_affected_revalidation(self) -> None:
        group = ProcessRepairGroup(
            "repair:incomplete",
            finding_ids=("finding:a",),
            root_cause_claim="one root cause",
            disproof_check_ids=("check:disprove",),
            affected_obligation_ids=("obligation:a",),
            owner_evidence_ids=("evidence:owner",),
            repair_action_ids=("repair",),
            required_revalidation_ids=("evidence:revalidation",),
            status="complete",
        )
        report = review_process_optimization(_decision(repair_groups=(group,)))
        self.assertTrue(
            any(code.endswith("revalidation_incomplete") for code in report.finding_codes)
        )

    def test_invalid_activation_reason_is_blocked(self) -> None:
        report = review_process_optimization(_decision(reasons=("always_optimize",)))
        self.assertIn("activation_reason_invalid", report.finding_codes)

    def test_public_surface_stays_within_the_complexity_budget(self) -> None:
        public_types = [
            name for name in strategy.__all__ if dataclasses.is_dataclass(getattr(strategy, name))
        ]
        self.assertEqual(len(public_types), 5)
        self.assertEqual(len(strategy.__all__), 6)
        source = Path(strategy.__file__).read_text(encoding="utf-8").splitlines()
        self.assertLessEqual(sum(bool(line.strip()) for line in source), 500)

    def test_report_serialization_preserves_bounded_fields(self) -> None:
        report = review_process_optimization(_decision())
        self.assertIsInstance(report, ProcessOptimizationReport)
        payload = report.to_dict()
        self.assertEqual(payload["status"], "selected")
        self.assertEqual(payload["selected_candidate_id"], "candidate:boundary-first")


if __name__ == "__main__":
    unittest.main()
