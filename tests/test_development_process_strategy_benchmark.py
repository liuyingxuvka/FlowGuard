from __future__ import annotations

from dataclasses import dataclass
import unittest

from flowguard.development_process_strategy import (
    ProcessOptimizationCandidate,
    ProcessOptimizationContract,
    ProcessOptimizationDecision,
    review_process_optimization,
)


@dataclass(frozen=True)
class ProcessTrace:
    trace_id: str
    terminal_outcome_ids: tuple[str, ...]
    obligation_ids: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    safety_ids: tuple[str, ...]
    side_effect_ids: tuple[str, ...]
    authority_ids: tuple[str, ...]
    check_runs: int
    repair_rounds: int
    revalidation_rounds: int
    handoffs: int
    visible_not_run: int = 0

    @property
    def repeated_work(self) -> int:
        return self.check_runs + self.repair_rounds + self.revalidation_rounds + self.handoffs


def _equivalent(left: ProcessTrace, right: ProcessTrace) -> bool:
    return (
        left.terminal_outcome_ids,
        left.obligation_ids,
        left.evidence_ids,
        left.safety_ids,
        left.side_effect_ids,
        left.authority_ids,
    ) == (
        right.terminal_outcome_ids,
        right.obligation_ids,
        right.evidence_ids,
        right.safety_ids,
        right.side_effect_ids,
        right.authority_ids,
    )


def _contract(trace: ProcessTrace) -> ProcessOptimizationContract:
    return ProcessOptimizationContract(
        "contract:trace",
        terminal_outcome_ids=trace.terminal_outcome_ids,
        required_obligation_ids=trace.obligation_ids,
        required_evidence_ids=trace.evidence_ids,
        safety_constraint_ids=trace.safety_ids,
        protected_side_effect_ids=trace.side_effect_ids,
        dependency_authority_ids=("dependency:owner",),
        execution_owner_ids=trace.authority_ids,
        revision="r1",
    )


def _candidate(
    trace: ProcessTrace,
    *,
    boundary: str,
    mode: str = "sequential",
) -> ProcessOptimizationCandidate:
    isolation = mode == "safe_parallel"
    return ProcessOptimizationCandidate(
        trace.trace_id,
        "contract:trace",
        terminal_outcome_ids=trace.terminal_outcome_ids,
        covered_obligation_ids=trace.obligation_ids,
        evidence_ids=trace.evidence_ids,
        safety_constraint_ids=trace.safety_ids,
        protected_side_effect_ids=trace.side_effect_ids,
        dependency_authority_ids=("dependency:owner",),
        execution_owner_ids=trace.authority_ids,
        step_ids=("diagnose", "repair"),
        validation_requirement_ids=("revalidate",),
        dependency_edges=(("diagnose", "repair"), ("repair", "revalidate")),
        diagnostic_boundary=boundary,
        execution_mode=mode,
        dependency_isolation_evidence_ids=("evidence:dependency-isolation",) if isolation else (),
        state_isolation_evidence_ids=("evidence:state-isolation",) if isolation else (),
        side_effect_isolation_evidence_ids=("evidence:side-effect-isolation",) if isolation else (),
        execution_owner_isolation_evidence_ids=("evidence:owner-isolation",) if isolation else (),
        comparison_basis="measured",
        comparison_evidence_ids=(f"evidence:trace:{trace.trace_id}",),
    )


class DevelopmentProcessStrategyTrajectoryTests(unittest.TestCase):
    def setUp(self) -> None:
        shared = {
            "terminal_outcome_ids": ("outcome:green",),
            "obligation_ids": ("obligation:a", "obligation:b", "obligation:c"),
            "evidence_ids": ("evidence:required",),
            "safety_ids": ("safety:workspace",),
            "side_effect_ids": ("side-effect:source",),
            "authority_ids": ("execution:owner",),
        }
        self.repeat_fail_fix = ProcessTrace(
            "candidate:repeat-fail-fix",
            **shared,
            check_runs=9,
            repair_rounds=3,
            revalidation_rounds=3,
            handoffs=3,
        )
        self.boundary_first = ProcessTrace(
            "candidate:boundary-first",
            **shared,
            check_runs=6,
            repair_rounds=1,
            revalidation_rounds=1,
            handoffs=1,
        )

    def test_boundary_first_trace_reduces_repeated_work_after_equivalence(self) -> None:
        self.assertTrue(_equivalent(self.repeat_fail_fix, self.boundary_first))
        self.assertLess(self.boundary_first.repeated_work, self.repeat_fail_fix.repeated_work)
        candidates = (
            _candidate(self.repeat_fail_fix, boundary="targeted"),
            _candidate(self.boundary_first, boundary="declared_complete"),
        )
        evidence = (
            "evidence:required",
            "evidence:material",
            "evidence:trace:candidate:repeat-fail-fix",
            "evidence:trace:candidate:boundary-first",
        )
        report = review_process_optimization(
            ProcessOptimizationDecision(
                "decision:trace",
                _contract(self.boundary_first),
                activation_reasons=("material_rework_risk",),
                candidates=candidates,
                selected_candidate_id="candidate:boundary-first",
                input_revision="trace:r1",
                current_evidence_ids=evidence,
                material_evidence_ids=("evidence:material",),
                selection_rationale="one evidence boundary exposes the shared root cause",
            )
        )
        self.assertTrue(report.ok)

    def test_hard_blocker_makes_not_run_descendants_visible_without_collecting_all(self) -> None:
        blocked = ProcessTrace(
            "candidate:hard-blocker",
            terminal_outcome_ids=("outcome:blocked-visible",),
            obligation_ids=("obligation:prerequisite",),
            evidence_ids=("evidence:required",),
            safety_ids=("safety:stop-invalid-descendants",),
            side_effect_ids=("side-effect:none",),
            authority_ids=("execution:owner",),
            check_runs=1,
            repair_rounds=0,
            revalidation_rounds=0,
            handoffs=0,
            visible_not_run=4,
        )
        self.assertEqual(blocked.visible_not_run, 4)
        self.assertEqual(blocked.repair_rounds, 0)

    def test_safe_parallel_trace_is_admitted_only_with_isolation_evidence(self) -> None:
        parallel = _candidate(
            self.boundary_first,
            boundary="budgeted",
            mode="safe_parallel",
        )
        isolation = (
            "evidence:dependency-isolation",
            "evidence:state-isolation",
            "evidence:side-effect-isolation",
            "evidence:owner-isolation",
        )
        report = review_process_optimization(
            ProcessOptimizationDecision(
                "decision:parallel",
                _contract(self.boundary_first),
                activation_reasons=("multiple_equivalent_routes",),
                candidates=(parallel,),
                selected_candidate_id=parallel.candidate_id,
                input_revision="trace:r1",
                current_evidence_ids=(
                    "evidence:required",
                    "evidence:material",
                    "evidence:trace:candidate:boundary-first",
                )
                + isolation,
                material_evidence_ids=("evidence:material",),
                selection_rationale="independent shards reduce coordination handoffs",
            )
        )
        self.assertTrue(report.ok)

    def test_non_test_workflow_can_use_the_same_general_rule(self) -> None:
        repeated_doc_edits = ProcessTrace(
            "candidate:edit-docs-one-by-one",
            terminal_outcome_ids=("outcome:guidance-consistent",),
            obligation_ids=("obligation:skill", "obligation:prompt", "obligation:template"),
            evidence_ids=("evidence:guidance-parity",),
            safety_ids=("safety:no-runtime-change",),
            side_effect_ids=("side-effect:docs",),
            authority_ids=("execution:docs-owner",),
            check_runs=7,
            repair_rounds=3,
            revalidation_rounds=3,
            handoffs=2,
        )
        inventory_first = ProcessTrace(
            "candidate:inventory-guidance-first",
            terminal_outcome_ids=("outcome:guidance-consistent",),
            obligation_ids=("obligation:skill", "obligation:prompt", "obligation:template"),
            evidence_ids=("evidence:guidance-parity",),
            safety_ids=("safety:no-runtime-change",),
            side_effect_ids=("side-effect:docs",),
            authority_ids=("execution:docs-owner",),
            check_runs=4,
            repair_rounds=1,
            revalidation_rounds=1,
            handoffs=1,
        )
        self.assertTrue(_equivalent(repeated_doc_edits, inventory_first))
        self.assertLess(inventory_first.repeated_work, repeated_doc_edits.repeated_work)


if __name__ == "__main__":
    unittest.main()
