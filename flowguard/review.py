"""Oracle review for deterministic scenarios."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Iterable, Sequence

from .export import to_jsonable
from .scenario import Scenario, ScenarioRun, run_exact_sequence
from .trace import Trace
from .workflow import Workflow


@dataclass(frozen=True)
class OracleReviewResult:
    """Expected-vs-observed result for one scenario."""

    scenario_name: str
    expected_summary: str
    observed_summary: str
    status: str
    evidence: tuple[str, ...] = ()
    counterexample_trace: Trace | None = None
    scenario_run: ScenarioRun | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "scenario_name": self.scenario_name,
            "expected_summary": self.expected_summary,
            "observed_summary": self.observed_summary,
            "status": self.status,
            "evidence": list(self.evidence),
            "counterexample_trace": (
                self.counterexample_trace.to_dict()
                if self.counterexample_trace is not None
                else None
            ),
            "scenario_run": (
                self.scenario_run.to_dict()
                if self.scenario_run is not None
                else None
            ),
        }


@dataclass(frozen=True)
class ScenarioReviewReport:
    """Aggregate review report for a scenario catalog."""

    ok: bool
    total_scenarios: int
    passed: int
    expected_violations_observed: int
    unexpected_violations: int
    missing_expected_violations: int
    needs_human_review: int
    known_limitations: int
    oracle_mismatches: int
    results: tuple[OracleReviewResult, ...]

    def format_text(self, max_counterexamples: int = 1) -> str:
        lines = [
            "=== flowguard scenario review ===",
            "",
            f"total: {self.total_scenarios}",
            f"passed: {self.passed}",
            f"expected violations observed: {self.expected_violations_observed}",
            f"unexpected violations: {self.unexpected_violations}",
            f"missing expected violations: {self.missing_expected_violations}",
            f"needs human review: {self.needs_human_review}",
            f"known limitations: {self.known_limitations}",
            f"oracle mismatches: {self.oracle_mismatches}",
            f"status: {'OK' if self.ok else 'MISMATCH'}",
        ]
        counterexamples_left = max_counterexamples
        for result in self.results:
            lines.extend(
                [
                    "",
                    f"Scenario: {result.scenario_name}",
                    f"Expected: {result.expected_summary}",
                    f"Observed: {result.observed_summary}",
                    f"Status: {result.status.upper()}",
                    "Evidence:",
                ]
            )
            for item in result.evidence:
                lines.append(f"  - {item}")
            if result.counterexample_trace is not None and counterexamples_left > 0:
                lines.extend(["Counterexample:", result.counterexample_trace.format_text()])
                counterexamples_left -= 1
        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "total_scenarios": self.total_scenarios,
            "passed": self.passed,
            "expected_violations_observed": self.expected_violations_observed,
            "unexpected_violations": self.unexpected_violations,
            "missing_expected_violations": self.missing_expected_violations,
            "needs_human_review": self.needs_human_review,
            "known_limitations": self.known_limitations,
            "oracle_mismatches": self.oracle_mismatches,
            "results": [result.to_dict() for result in self.results],
        }

    def to_json_text(self, indent: int = 2) -> str:
        return json.dumps(to_jsonable(self.to_dict()), indent=indent, sort_keys=True)


def _expected_summary(scenario: Scenario) -> str:
    expectation = scenario.expected
    if expectation.summary:
        return expectation.summary
    pieces = [expectation.expected_status.upper()]
    if expectation.expected_violation_names:
        pieces.append(",".join(expectation.expected_violation_names))
    if expectation.required_trace_labels:
        pieces.append("requires labels " + ",".join(expectation.required_trace_labels))
    return "; ".join(pieces)


def _observed_summary(run: ScenarioRun) -> str:
    pieces = [run.observed_status.upper()]
    if run.observed_violation_names:
        pieces.append(",".join(run.observed_violation_names))
    return "; ".join(pieces)


def _labels_present(run: ScenarioRun) -> set[str]:
    labels: set[str] = set()
    for trace in run.traces:
        labels.update(trace.labels)
    return labels


def _counterexample(run: ScenarioRun) -> Trace | None:
    if run.model_report.violations:
        return run.model_report.violations[0].trace
    if run.model_report.dead_branches:
        return run.model_report.dead_branches[0].trace
    if run.traces:
        return run.traces[0]
    return None


def review_scenario(
    scenario: Scenario,
    default_workflow: Workflow | None = None,
    default_invariants: Sequence[Any] = (),
) -> OracleReviewResult:
    workflow = scenario.workflow or default_workflow
    if workflow is None:
        raise ValueError(f"scenario {scenario.name!r} has no workflow")
    invariants = scenario.invariants or tuple(default_invariants)
    run = run_exact_sequence(
        workflow=workflow,
        initial_state=scenario.initial_state,
        external_input_sequence=scenario.external_input_sequence,
        invariants=invariants,
        scenario=scenario,
    )

    expectation = scenario.expected
    labels = _labels_present(run)
    missing_labels = tuple(label for label in expectation.required_trace_labels if label not in labels)
    forbidden_labels = tuple(label for label in expectation.forbidden_trace_labels if label in labels)
    missing_evidence = tuple(
        expected
        for expected in expectation.required_evidence
        if not any(expected in item for item in run.evidence)
    )
    failed_custom = tuple(result for result in run.oracle_check_results if not result.ok)

    evidence = list(run.evidence)
    evidence.append(f"observed labels: {','.join(sorted(labels))}" if labels else "observed labels: (none)")
    if missing_labels:
        evidence.append(f"missing required labels: {missing_labels!r}")
    if forbidden_labels:
        evidence.append(f"forbidden labels observed: {forbidden_labels!r}")
    if missing_evidence:
        evidence.append(f"missing required evidence: {missing_evidence!r}")
    for result in failed_custom:
        evidence.append(result.message)

    expected_status = expectation.expected_status
    expected_names = set(expectation.expected_violation_names)
    observed_names = set(run.observed_violation_names)

    if expected_status in {"needs_human_review", "human_review"}:
        status = "needs_human_review"
    elif expected_status in {"known_limitation", "limitation"}:
        status = "known_limitation"
    elif missing_labels or forbidden_labels or missing_evidence:
        status = "oracle_mismatch"
    elif expected_status in {"violation", "expected_violation"}:
        if run.observed_status == "ok":
            status = "missing_expected_violation"
        elif expected_names and not expected_names.issubset(observed_names):
            status = "oracle_mismatch"
            evidence.append(
                f"expected violations {tuple(sorted(expected_names))!r}, observed {tuple(sorted(observed_names))!r}"
            )
        else:
            status = "expected_violation_observed"
    elif expected_status == "ok":
        if failed_custom:
            status = "oracle_mismatch"
        elif run.observed_status != "ok":
            status = "unexpected_violation"
        else:
            status = "pass"
    else:
        status = "oracle_mismatch"
        evidence.append(f"unknown expected status: {expected_status}")

    return OracleReviewResult(
        scenario_name=scenario.name,
        expected_summary=_expected_summary(scenario),
        observed_summary=_observed_summary(run),
        status=status,
        evidence=tuple(evidence),
        counterexample_trace=_counterexample(run) if status != "pass" else None,
        scenario_run=run,
    )


def review_scenarios(
    scenarios: Iterable[Scenario],
    default_workflow: Workflow | None = None,
    default_invariants: Sequence[Any] = (),
) -> ScenarioReviewReport:
    results = tuple(
        review_scenario(
            scenario,
            default_workflow=default_workflow,
            default_invariants=default_invariants,
        )
        for scenario in scenarios
    )
    unexpected = sum(1 for result in results if result.status == "unexpected_violation")
    missing = sum(1 for result in results if result.status == "missing_expected_violation")
    mismatches = sum(1 for result in results if result.status == "oracle_mismatch")
    ok = unexpected == 0 and missing == 0 and mismatches == 0
    return ScenarioReviewReport(
        ok=ok,
        total_scenarios=len(results),
        passed=sum(1 for result in results if result.status == "pass"),
        expected_violations_observed=sum(
            1 for result in results if result.status == "expected_violation_observed"
        ),
        unexpected_violations=unexpected,
        missing_expected_violations=missing,
        needs_human_review=sum(1 for result in results if result.status == "needs_human_review"),
        known_limitations=sum(1 for result in results if result.status == "known_limitation"),
        oracle_mismatches=mismatches,
        results=results,
    )


__all__ = [
    "OracleReviewResult",
    "ScenarioReviewReport",
    "review_scenario",
    "review_scenarios",
]
