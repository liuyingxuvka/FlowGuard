"""Current evidence baseline for flowguard Phase 10.5."""

from __future__ import annotations

import unittest
from pathlib import Path
from typing import Iterable

from flowguard.baseline import EvidenceCaseResult, EvidenceBaselineReport, build_evidence_baseline_report
from flowguard.report import CheckReport
from flowguard.review import review_scenarios

from examples.job_matching.conformance import (
    generate_representative_traces,
    replay_job_matching_trace,
)
from examples.job_matching.model import (
    BrokenRecordScoredJob,
    BrokenScoreJob,
    build_workflow,
    check_job_matching_model,
)
from examples.job_matching.production import (
    BrokenDuplicateRecordSystem,
    BrokenRepeatedScoringSystem,
    CorrectJobMatchingSystem,
)
from examples.job_matching.scenarios import all_job_matching_scenarios
from examples.looping_workflow.model import run_loop_review


WORKSPACE_ROOT = Path(__file__).resolve().parents[2]


def _scenario_bug_class(name: str) -> str:
    if name.startswith("S13"):
        return "identity_conflict_policy"
    if name.startswith("B01") or name.startswith("B02"):
        return "duplicate_side_effect"
    if name.startswith("B03") or name.startswith("B04"):
        return "repeated_processing_without_refresh"
    if name.startswith("B05"):
        return "low_score_recording"
    if name.startswith("B06") or name.startswith("B13"):
        return "contradictory_decision"
    if name.startswith("B07"):
        return "missing_decision"
    if name.startswith("B08"):
        return "downstream_non_consumable_output"
    if name.startswith("B09") or name.startswith("B14"):
        return "source_traceability"
    if name.startswith("B10"):
        return "cache_consistency"
    if name.startswith("B11"):
        return "state_owner_boundary"
    if name.startswith("B12"):
        return "duplicate_decision"
    if name.startswith("B15"):
        return "projection_anti_pattern"
    if "same_job" in name or "repeat" in name or name.startswith("S04") or name.startswith("S12"):
        return "idempotency_regression"
    return "expected_ok_workflow"


def job_matching_scenario_cases() -> tuple[EvidenceCaseResult, ...]:
    report = review_scenarios(all_job_matching_scenarios())
    return tuple(
        EvidenceCaseResult(
            name=result.scenario_name,
            group="scenario:job_matching",
            bug_class=_scenario_bug_class(result.scenario_name),
            expected=result.expected_summary,
            observed=result.observed_summary,
            status=result.status,
            evidence=result.evidence,
        )
        for result in report.results
    )


def _loop_bug_class(status: str, expected_summary: str, name: str) -> str:
    if "potential_nontermination" in expected_summary or "missing_progress_guarantee" in expected_summary:
        return "progress_fairness"
    if "stuck_state" in expected_summary:
        return "stuck_state"
    if "unreachable_success" in expected_summary:
        return "unreachable_success"
    if "terminal_with_outgoing_edges" in expected_summary:
        return "terminal_semantics"
    if "non_terminating_component" in expected_summary:
        return "non_terminating_component"
    if name.startswith("L03") or name.startswith("L10"):
        return "bounded_terminal_ok"
    return "loop_expected_ok"


def loop_review_cases() -> tuple[EvidenceCaseResult, ...]:
    report = run_loop_review()
    return tuple(
        EvidenceCaseResult(
            name=result.scenario_name,
            group="loop:looping_workflow",
            bug_class=_loop_bug_class(result.status, result.expected_summary, result.scenario_name),
            expected=result.expected_summary,
            observed=result.observed_summary,
            status=result.status,
            evidence=result.evidence,
        )
        for result in report.results
    )


def _status_for_expected_ok(actual_ok: bool, expected_ok: bool) -> str:
    if expected_ok and actual_ok:
        return "pass"
    if expected_ok and not actual_ok:
        return "unexpected_violation"
    if not expected_ok and not actual_ok:
        return "expected_violation_observed"
    return "missing_expected_violation"


def _check_report_case(
    name: str,
    report: CheckReport,
    *,
    expected_ok: bool,
    bug_class: str,
) -> EvidenceCaseResult:
    return EvidenceCaseResult(
        name=name,
        group="model_check:job_matching",
        bug_class=bug_class,
        expected="OK" if expected_ok else "VIOLATION",
        observed="OK" if report.ok else "VIOLATION",
        status=_status_for_expected_ok(report.ok, expected_ok),
        evidence=(
            f"traces={len(report.traces)}",
            f"violations={len(report.violations)}",
            f"dead_branches={len(report.dead_branches)}",
            f"exceptions={len(report.exception_branches)}",
        ),
    )


def model_check_cases() -> tuple[EvidenceCaseResult, ...]:
    return (
        _check_report_case(
            "M01_job_matching_correct_model",
            check_job_matching_model(max_sequence_length=2),
            expected_ok=True,
            bug_class="model_invariant_regression",
        ),
        _check_report_case(
            "M02_job_matching_broken_duplicate_record_model",
            check_job_matching_model(
                workflow=build_workflow(record_block=BrokenRecordScoredJob()),
                max_sequence_length=2,
            ),
            expected_ok=False,
            bug_class="duplicate_side_effect",
        ),
        _check_report_case(
            "M03_job_matching_broken_repeated_scoring_model",
            check_job_matching_model(
                workflow=build_workflow(score_block=BrokenScoreJob()),
                max_sequence_length=2,
            ),
            expected_ok=False,
            bug_class="repeated_processing_without_refresh",
        ),
    )


def conformance_cases() -> tuple[EvidenceCaseResult, ...]:
    traces = generate_representative_traces()
    system_cases = (
        (
            "correct_production",
            CorrectJobMatchingSystem,
            "production_conformance_ok",
            lambda trace: True,
        ),
        (
            "broken_duplicate_record_production",
            BrokenDuplicateRecordSystem,
            "duplicate_side_effect",
            lambda trace: not (trace.has_label("record_added") and trace.has_label("record_already_exists")),
        ),
        (
            "broken_repeated_scoring_production",
            BrokenRepeatedScoringSystem,
            "repeated_processing_without_refresh",
            lambda trace: not trace.has_label("score_cached"),
        ),
    )
    results: list[EvidenceCaseResult] = []
    for system_name, system_factory, bug_class, expected_ok_for_trace in system_cases:
        for index, trace in enumerate(traces, start=1):
            expected_ok = bool(expected_ok_for_trace(trace))
            report = replay_job_matching_trace(trace, system_factory())
            first_violation = report.violations[0] if report.violations else None
            evidence = [
                f"trace_index={index}",
                f"replayed_steps={len(report.replayed_steps)}",
                f"violations={len(report.violations)}",
                f"trigger_labels={','.join(trace.labels)}",
            ]
            if first_violation is not None:
                evidence.append(f"first_violation={first_violation.rule_name}: {first_violation.message}")
            results.append(
                EvidenceCaseResult(
                    name=f"C{len(results) + 1:02d}_{system_name}_trace_{index}",
                    group="conformance:job_matching",
                    bug_class=bug_class,
                    expected="OK" if expected_ok else "VIOLATION",
                    observed="OK" if report.ok else "VIOLATION",
                    status=_status_for_expected_ok(report.ok, expected_ok),
                    evidence=tuple(evidence),
                )
            )
    return tuple(results)


def _iter_test_ids(suite: unittest.TestSuite) -> Iterable[str]:
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            yield from _iter_test_ids(item)
        else:
            yield item.id()


def _unit_bug_class(test_id: str) -> str:
    lowered = test_id.lower()
    if "conformance" in lowered:
        return "conformance_replay"
    if "scenario" in lowered or "oracle" in lowered:
        return "scenario_oracle"
    if "loop" in lowered:
        return "loop_detection"
    if "duplicate" in lowered:
        return "duplicate_side_effect"
    if "repeated_scoring" in lowered:
        return "repeated_processing_without_refresh"
    if "trace_export" in lowered:
        return "trace_export"
    if "workflow" in lowered:
        return "workflow_branching"
    if "invariant" in lowered:
        return "invariant_checking"
    if "counterexample" in lowered:
        return "counterexample_trace"
    if "core" in lowered:
        return "core_contract"
    return "unit_regression_inventory"


def unit_test_inventory_cases(tests_dir: Path | None = None) -> tuple[EvidenceCaseResult, ...]:
    root = tests_dir or (WORKSPACE_ROOT / "tests")
    suite = unittest.defaultTestLoader.discover(str(root))
    test_ids = tuple(sorted(_iter_test_ids(suite)))
    return tuple(
        EvidenceCaseResult(
            name=f"U{index:03d}_{test_id}",
            group="unit_test_inventory",
            bug_class=_unit_bug_class(test_id),
            expected="test is present and is run by python -m unittest discover -s tests",
            observed="discovered",
            status="pass",
            evidence=("inventory case; execution is validated by the unittest command",),
            metadata=(("test_id", test_id),),
        )
        for index, test_id in enumerate(test_ids, start=1)
    )


def all_evidence_cases() -> tuple[EvidenceCaseResult, ...]:
    return (
        job_matching_scenario_cases()
        + loop_review_cases()
        + conformance_cases()
        + model_check_cases()
        + unit_test_inventory_cases()
    )


def build_current_evidence_baseline(target_cases: int = 100) -> EvidenceBaselineReport:
    return build_evidence_baseline_report(
        all_evidence_cases(),
        target_cases=target_cases,
        summary=(
            "Phase 10.5 baseline: unit inventory, job_matching scenarios, "
            "job_matching conformance, model checks, and loop/stuck review."
        ),
    )


__all__ = [
    "all_evidence_cases",
    "build_current_evidence_baseline",
    "conformance_cases",
    "job_matching_scenario_cases",
    "loop_review_cases",
    "model_check_cases",
    "unit_test_inventory_cases",
]
