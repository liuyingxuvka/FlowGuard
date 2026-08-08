from __future__ import annotations

import ast
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
        "step_artifact_reads": (("diagnose", "artifact:source"), ("repair", "artifact:finding")),
        "step_artifact_writes": (("diagnose", "artifact:finding"), ("repair", "artifact:patch")),
        "step_validation_ids": (("repair", "revalidate"),),
        "step_execution_owner_ids": (("diagnose", "execution:owner"), ("repair", "execution:owner")),
        "step_side_effect_ids": (("repair", "side-effect:workspace"),),
        "step_effort_costs": (("diagnose", 1.0), ("repair", 1.0)),
        "step_effort_evidence_ids": (("diagnose", "evidence:cost:diagnose"), ("repair", "evidence:cost:repair")),
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
        "evidence:cost:diagnose",
        "evidence:cost:repair",
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
        self.assertIn("Pareto-dominating process candidate", report.selection_rationale)
        self.assertNotIn("total", report.cost_component_ids)
        self.assertEqual(
            report.caller_selection_rationale,
            "collect related evidence before one root-cause repair",
        )

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
            any(
                code.endswith("obligation_boundary_mismatch")
                for code in report.rejected_candidate_finding_codes
            )
        )

    def test_dependency_cycle_blocks_candidate(self) -> None:
        candidate = _candidate(
            dependency_edges=(("diagnose", "repair"), ("repair", "diagnose"))
        )
        report = review_process_optimization(_decision(candidates=(candidate,)))
        self.assertTrue(any(
            code.endswith("dependency_cycle")
            for code in report.rejected_candidate_finding_codes
        ))

    def test_declared_step_order_must_linearize_dependencies(self) -> None:
        candidate = _candidate(step_ids=("repair", "diagnose"))
        report = review_process_optimization(_decision(candidates=(candidate,)))
        self.assertTrue(any(
            code.endswith("declared_order_not_dependency_linearization")
            for code in report.rejected_candidate_finding_codes
        ))

    def test_measured_candidate_requires_cost_and_cost_evidence_for_every_step(self) -> None:
        candidate = _candidate(
            comparison_basis="measured",
            step_effort_costs=(("diagnose", 1.0),),
        )
        report = review_process_optimization(_decision(candidates=(candidate,)))
        self.assertTrue(any(
            code.endswith("measured_step_cost_missing")
            for code in report.rejected_candidate_finding_codes
        ))

    def test_invalid_nonselected_candidate_is_rejected_without_blocking_valid_selection(self) -> None:
        invalid = _candidate(
            "candidate:invalid",
            covered_obligation_ids=("obligation:a",),
        )
        valid = _candidate("candidate:valid")
        report = review_process_optimization(_decision(
            candidates=(invalid, valid), selected="candidate:valid"
        ))
        self.assertTrue(report.ok)
        self.assertEqual(report.selected_candidate_id, "candidate:valid")
        self.assertEqual(report.eligible_candidate_ids, ("candidate:valid",))
        self.assertEqual(report.rejected_candidate_ids, ("candidate:invalid",))
        self.assertTrue(any(
            code.endswith("obligation_boundary_mismatch")
            for code in report.rejected_candidate_finding_codes
        ))

    def test_caller_pointing_to_rejected_candidate_blocks_even_when_valid_alternative_exists(self) -> None:
        invalid = _candidate(
            "candidate:invalid",
            covered_obligation_ids=("obligation:a",),
        )
        valid = _candidate("candidate:valid")
        report = review_process_optimization(_decision(
            candidates=(invalid, valid), selected="candidate:invalid"
        ))
        self.assertFalse(report.ok)
        self.assertEqual(report.selected_candidate_id, "candidate:valid")
        self.assertIn("selected_candidate_ineligible", report.finding_codes)

    def test_unique_dominating_candidate_is_selected_and_dominated_caller_choice_is_rejected(self) -> None:
        expensive = _candidate(
            "candidate:expensive",
            step_effort_costs=(("diagnose", 3.0), ("repair", 3.0)),
        )
        cheaper = _candidate("candidate:cheaper")
        report = review_process_optimization(_decision(
            candidates=(expensive, cheaper), selected="candidate:expensive"
        ))
        self.assertFalse(report.ok)
        self.assertEqual(report.selected_candidate_id, "candidate:cheaper")
        self.assertIn("caller_selected_candidate_dominated", report.finding_codes)

    def test_equal_cost_vectors_remain_visible_as_unresolved_non_dominated_candidates(self) -> None:
        first = _candidate("candidate:first")
        second = _candidate("candidate:second")
        report = review_process_optimization(_decision(
            candidates=(first, second), selected="candidate:first"
        ))
        self.assertFalse(report.ok)
        self.assertEqual(report.status, "needs_evidence")
        self.assertEqual(report.selected_candidate_id, "")
        self.assertEqual(
            report.non_dominated_candidate_ids,
            ("candidate:first", "candidate:second"),
        )

    def test_process_cost_tradeoff_cannot_be_collapsed_to_a_scalar_total(self) -> None:
        lower_effort_more_effects = _candidate(
            "candidate:lower-effort",
            step_side_effect_ids=(
                ("diagnose", "side-effect:workspace"),
                ("repair", "side-effect:workspace"),
            ),
        )
        fewer_effects_more_effort = _candidate(
            "candidate:fewer-effects",
            step_effort_costs=(("diagnose", 3.0), ("repair", 3.0)),
        )
        report = review_process_optimization(
            _decision(
                candidates=(lower_effort_more_effects, fewer_effects_more_effort),
                selected="candidate:lower-effort",
            )
        )
        self.assertFalse(report.ok)
        self.assertEqual(report.selected_candidate_id, "")
        self.assertIn("candidate_cost_tradeoff_unresolved", report.finding_codes)
        self.assertIn(
            "caller_selection_cannot_break_non_dominated_boundary",
            report.finding_codes,
        )
        self.assertEqual(
            set(report.non_dominated_candidate_ids),
            {"candidate:lower-effort", "candidate:fewer-effects"},
        )

    def test_missing_effort_dimension_stays_incomparable_instead_of_becoming_zero(self) -> None:
        incomplete = _candidate(
            "candidate:incomplete",
            step_effort_costs=(),
        )
        complete = _candidate("candidate:complete")
        report = review_process_optimization(
            _decision(candidates=(incomplete, complete), selected="")
        )
        self.assertFalse(report.ok)
        self.assertIn("candidate_cost_vector_incomplete", report.finding_codes)
        rows = {str(row[0]): row[1:] for row in report.candidate_cost_rows}
        self.assertIsNone(rows["candidate:incomplete"][-1])

    def test_freeze_first_beats_interleaved_derived_artifact_rework(self) -> None:
        interleaved = _candidate(
            "candidate:interleaved",
            step_ids=("write_docs_early", "update_source", "write_docs_current"),
            validation_requirement_ids=("validate_docs",),
            dependency_edges=(("write_docs_early", "update_source"), ("update_source", "write_docs_current"), ("write_docs_current", "validate_docs")),
            step_artifact_reads=(("write_docs_early", "artifact:source"), ("write_docs_current", "artifact:source")),
            step_artifact_writes=(("write_docs_early", "artifact:docs"), ("update_source", "artifact:source"), ("write_docs_current", "artifact:docs")),
            step_artifact_invalidations=(("update_source", "artifact:docs"),),
            step_validation_ids=(("write_docs_early", "validate_docs"), ("write_docs_current", "validate_docs")),
            step_execution_owner_ids=(("write_docs_early", "execution:owner"), ("update_source", "execution:owner"), ("write_docs_current", "execution:owner")),
            step_side_effect_ids=(("write_docs_early", "side-effect:workspace"), ("update_source", "side-effect:workspace"), ("write_docs_current", "side-effect:workspace")),
            step_effort_costs=(("write_docs_early", 1.0), ("update_source", 1.0), ("write_docs_current", 1.0)),
            step_effort_evidence_ids=(("write_docs_early", "evidence:cost:docs-early"), ("update_source", "evidence:cost:update"), ("write_docs_current", "evidence:cost:docs-current")),
            comparison_basis="measured",
        )
        freeze_first = _candidate(
            "candidate:freeze-first",
            step_ids=("update_source", "write_docs_current"),
            validation_requirement_ids=("validate_docs",),
            dependency_edges=(("update_source", "write_docs_current"), ("write_docs_current", "validate_docs")),
            step_artifact_reads=(("write_docs_current", "artifact:source"),),
            step_artifact_writes=(("update_source", "artifact:source"), ("write_docs_current", "artifact:docs")),
            step_artifact_invalidations=(("update_source", "artifact:docs"),),
            step_validation_ids=(("write_docs_current", "validate_docs"),),
            step_execution_owner_ids=(("update_source", "execution:owner"), ("write_docs_current", "execution:owner")),
            step_side_effect_ids=(("update_source", "side-effect:workspace"), ("write_docs_current", "side-effect:workspace")),
            step_effort_costs=(("update_source", 1.0), ("write_docs_current", 1.0)),
            step_effort_evidence_ids=(("update_source", "evidence:cost:update"), ("write_docs_current", "evidence:cost:docs-current")),
            comparison_basis="measured",
        )
        current = (
            "evidence:required", "evidence:comparison", "evidence:material",
            "evidence:cost:docs-early", "evidence:cost:update", "evidence:cost:docs-current",
        )
        report = review_process_optimization(_decision(
            candidates=(interleaved, freeze_first), selected="", current_evidence_ids=current
        ))
        self.assertTrue(report.ok)
        self.assertEqual(report.selected_candidate_id, "candidate:freeze-first")
        costs = {str(row[0]): row[1:] for row in report.candidate_cost_rows}
        self.assertEqual(costs["candidate:interleaved"], (1.0, 1.0, 1.0, 0.0, 3.0, 3.0))
        self.assertEqual(costs["candidate:freeze-first"], (0.0, 0.0, 0.0, 0.0, 2.0, 2.0))

    def test_safe_parallel_requires_four_isolation_evidence_boundaries(self) -> None:
        candidate = _candidate(execution_mode="safe_parallel")
        report = review_process_optimization(_decision(candidates=(candidate,)))
        self.assertTrue(
            any(
                code.endswith("parallel_isolation_evidence_missing")
                for code in report.rejected_candidate_finding_codes
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
                    "evidence:cost:diagnose",
                    "evidence:cost:repair",
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
            "candidate:candidate:boundary-first:current_evidence_reference_missing:comparison",
            report.rejected_candidate_finding_codes,
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
                    "evidence:cost:diagnose",
                    "evidence:cost:repair",
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
        source = Path(strategy.__file__).read_text(encoding="utf-8")
        tree = ast.parse(source)
        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                declaration_lines = [
                    child.lineno for child in node.body if isinstance(child, ast.AnnAssign)
                ]
                self.assertEqual(len(declaration_lines), len(set(declaration_lines)))

    def test_report_serialization_preserves_bounded_fields(self) -> None:
        report = review_process_optimization(_decision())
        self.assertIsInstance(report, ProcessOptimizationReport)
        payload = report.to_dict()
        self.assertEqual(payload["status"], "selected")
        self.assertEqual(payload["selected_candidate_id"], "candidate:boundary-first")


if __name__ == "__main__":
    unittest.main()
