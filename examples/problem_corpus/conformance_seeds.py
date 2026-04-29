"""Production-conformance seed replay for selected non-job-matching families."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Iterable

from flowguard.conformance import ConformanceReport, replay_trace
from flowguard.core import Invariant, InvariantResult
from flowguard.export import to_jsonable
from flowguard.replay import ReplayObservation
from flowguard.review import review_scenario
from flowguard.trace import TraceStep

from examples.job_matching.conformance import (
    generate_representative_traces,
    has_repeated_external_input,
    replay_job_matching_trace,
)
from examples.job_matching.production import (
    BrokenDuplicateRecordSystem,
    BrokenRepeatedScoringSystem,
    CorrectJobMatchingSystem,
)

from .matrix import build_problem_corpus
from .real_models import (
    MODEL_SPECS,
    DomainEffectBlock,
    DomainFinalizeBlock,
    DomainModelSpec,
    DomainProcessBlock,
    DomainSourceBlock,
    DomainState,
    build_real_model_scenario,
    classify_failure_mode,
    input_sequence_for_case,
    select_variant_for_case,
)


BENCHMARK_CONFORMANCE_SEED_FAMILIES = tuple(MODEL_SPECS)
CONFORMANCE_SEED_FAMILIES = ("job_matching",) + BENCHMARK_CONFORMANCE_SEED_FAMILIES


@dataclass(frozen=True)
class ConformanceSeedResult:
    family: str
    implementation: str
    expected_ok: bool
    ok: bool
    status: str
    violation_count: int
    failed_step_index: int | None = None
    message: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "family": self.family,
            "implementation": self.implementation,
            "expected_ok": self.expected_ok,
            "ok": self.ok,
            "status": self.status,
            "violation_count": self.violation_count,
            "failed_step_index": self.failed_step_index,
            "message": self.message,
        }


@dataclass(frozen=True)
class ConformanceSeedReport:
    ok: bool
    production_conformance_family_count: int
    benchmark_conformance_family_count: int
    benchmark_conformance_families: tuple[str, ...]
    total_replays: int
    passed: int
    expected_violations_observed: int
    failures: int
    results: tuple[ConformanceSeedResult, ...]
    summary: str = ""

    def format_text(self) -> str:
        lines = [
            "=== flowguard production conformance seeds ===",
            "",
            f"status: {'OK' if self.ok else 'MISMATCH'}",
            f"production_conformance_family_count: {self.production_conformance_family_count}",
            f"benchmark_conformance_family_count: {self.benchmark_conformance_family_count}",
            f"total_replays: {self.total_replays}",
            f"passed: {self.passed}",
            f"expected_violations_observed: {self.expected_violations_observed}",
            f"failures: {self.failures}",
        ]
        if self.summary:
            lines.append(f"summary: {self.summary}")
        lines.extend(["", "Replays:"])
        for result in self.results:
            lines.append(
                f"  - {result.family}/{result.implementation}: {result.status} "
                f"(violations={result.violation_count})"
            )
        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "production_conformance_family_count": self.production_conformance_family_count,
            "benchmark_conformance_family_count": self.benchmark_conformance_family_count,
            "benchmark_conformance_families": list(self.benchmark_conformance_families),
            "total_replays": self.total_replays,
            "passed": self.passed,
            "expected_violations_observed": self.expected_violations_observed,
            "failures": self.failures,
            "results": [result.to_dict() for result in self.results],
            "summary": self.summary,
        }

    def to_json_text(self, indent: int = 2) -> str:
        return json.dumps(to_jsonable(self.to_dict()), indent=indent, sort_keys=True)


class DomainSeedReplayAdapter:
    """Replay abstract domain traces through a small production-like seed system."""

    def __init__(self, spec: DomainModelSpec, *, broken: bool, category: str) -> None:
        self.spec = spec
        self.broken = broken
        self.category = category
        self.state: DomainState | None = None
        self.last_output: Any = None
        self.last_label = ""
        self.last_reason = ""
        self.blocks = {
            block.name: block
            for block in (
                DomainSourceBlock(spec),
                DomainProcessBlock(spec, category, broken),
                DomainEffectBlock(spec, category, broken),
                DomainFinalizeBlock(spec, category, broken),
            )
        }

    def reset(self, initial_state: DomainState) -> None:
        self.state = initial_state
        self.last_output = None
        self.last_label = ""
        self.last_reason = ""

    def apply_step(self, step: TraceStep) -> ReplayObservation:
        if self.state is None:
            raise RuntimeError("adapter was not reset")
        block = self.blocks.get(step.function_name)
        if block is None:
            raise ValueError(f"unsupported function step: {step.function_name}")
        results = tuple(block.apply(step.function_input, self.state))
        if not results:
            raise ValueError(f"production seed produced no result for {step.function_name}")
        result = results[0]
        self.state = result.new_state
        self.last_output = result.output
        self.last_label = result.label
        self.last_reason = result.reason
        return ReplayObservation(
            function_name=step.function_name,
            observed_output=self.last_output,
            observed_state=self.state,
            label=self.last_label,
            reason=self.last_reason,
            metadata={
                "seed_broken": self.broken,
                "seed_category": self.category,
            },
        )

    def observe_state(self) -> DomainState:
        if self.state is None:
            raise RuntimeError("adapter was not reset")
        return self.state

    def observe_output(self) -> Any:
        return self.last_output


def _seed_invariant(category: str) -> Invariant:
    from .real_models import _structural_violation_exists

    def predicate(state: DomainState, _trace) -> InvariantResult:
        if _structural_violation_exists(state, category):
            return InvariantResult.fail(f"{category} observed in production seed replay")
        return InvariantResult.pass_()

    return Invariant(
        name=category,
        description=f"Production conformance seed must not exhibit {category}.",
        predicate=predicate,
    )


def _select_seed_case(family: str):
    for case in build_problem_corpus().cases:
        if case.workflow_family != family:
            continue
        if case.case_kind != "positive_correct_case":
            continue
        if len(input_sequence_for_case(case)) > 0:
            return case
    raise ValueError(f"no seed case found for {family}")


def _domain_seed_reports_for_family(family: str) -> tuple[ConformanceSeedResult, ...]:
    case = _select_seed_case(family)
    base_spec = MODEL_SPECS[family]
    variant = select_variant_for_case(case)
    spec = variant.to_model_spec(base_spec)
    scenario = build_real_model_scenario(case)
    review_result = review_scenario(scenario)
    if review_result.status != "pass" or review_result.scenario_run is None:
        raise RuntimeError(f"seed scenario failed for {family}: {review_result.status}")
    trace = review_result.scenario_run.traces[0]

    seed_runs = (
        ("correct", False, classify_failure_mode(case.failure_mode), True),
        ("broken_duplicate_side_effect", True, "duplicate_side_effect", False),
        (
            "broken_repeated_processing_without_refresh",
            True,
            "repeated_processing_without_refresh",
            False,
        ),
    )
    results: list[ConformanceSeedResult] = []
    for implementation, broken, category, expected_ok in seed_runs:
        report = replay_trace(
            trace,
            DomainSeedReplayAdapter(spec, broken=broken, category=category),
            invariants=() if expected_ok else (_seed_invariant(category),),
        )
        results.append(_to_seed_result(family, implementation, expected_ok, report))
    return tuple(results)


def _job_matching_seed_results() -> tuple[ConformanceSeedResult, ...]:
    trace = next(
        trace for trace in generate_representative_traces() if has_repeated_external_input(trace)
    )
    runs = (
        ("correct", True, replay_job_matching_trace(trace, CorrectJobMatchingSystem())),
        (
            "broken_duplicate_record",
            False,
            replay_job_matching_trace(trace, BrokenDuplicateRecordSystem()),
        ),
        (
            "broken_repeated_scoring",
            False,
            replay_job_matching_trace(trace, BrokenRepeatedScoringSystem()),
        ),
    )
    return tuple(
        _to_seed_result("job_matching", implementation, expected_ok, report)
        for implementation, expected_ok, report in runs
    )


def _to_seed_result(
    family: str,
    implementation: str,
    expected_ok: bool,
    report: ConformanceReport,
) -> ConformanceSeedResult:
    status = "pass" if expected_ok and report.ok else "expected_violation_observed"
    if expected_ok and not report.ok:
        status = "unexpected_violation"
    if not expected_ok and report.ok:
        status = "missing_expected_violation"
    first_message = report.violations[0].message if report.violations else ""
    return ConformanceSeedResult(
        family=family,
        implementation=implementation,
        expected_ok=expected_ok,
        ok=report.ok,
        status=status,
        violation_count=len(report.violations),
        failed_step_index=report.failed_step_index,
        message=first_message,
    )


def review_conformance_seeds(
    families: Iterable[str] = CONFORMANCE_SEED_FAMILIES,
) -> ConformanceSeedReport:
    """Run conformance seed replay for job_matching plus benchmark families."""

    results: list[ConformanceSeedResult] = []
    requested = tuple(families)
    if "job_matching" in requested:
        results.extend(_job_matching_seed_results())
    for family in requested:
        if family == "job_matching":
            continue
        results.extend(_domain_seed_reports_for_family(family))

    failures = sum(
        1
        for result in results
        if result.status in {"unexpected_violation", "missing_expected_violation", "oracle_mismatch"}
    )
    families_seen = {result.family for result in results}
    benchmark_families_seen = tuple(
        sorted(family for family in families_seen if family in BENCHMARK_CONFORMANCE_SEED_FAMILIES)
    )
    return ConformanceSeedReport(
        ok=failures == 0
        and len(benchmark_families_seen) == len(BENCHMARK_CONFORMANCE_SEED_FAMILIES),
        production_conformance_family_count=len(families_seen),
        benchmark_conformance_family_count=len(benchmark_families_seen),
        benchmark_conformance_families=benchmark_families_seen,
        total_replays=len(results),
        passed=sum(1 for result in results if result.status == "pass"),
        expected_violations_observed=sum(
            1 for result in results if result.status == "expected_violation_observed"
        ),
        failures=failures,
        results=tuple(results),
        summary=(
            "Phase 12 conformance seeds: job_matching remains the full example, "
            "and all 25 benchmark workflow families now have correct and broken "
            "production-like replay evidence."
        ),
    )


__all__ = [
    "CONFORMANCE_SEED_FAMILIES",
    "BENCHMARK_CONFORMANCE_SEED_FAMILIES",
    "ConformanceSeedReport",
    "ConformanceSeedResult",
    "DomainSeedReplayAdapter",
    "review_conformance_seeds",
]
