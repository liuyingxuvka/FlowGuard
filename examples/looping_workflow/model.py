"""Small loop/stuck-state models for flowguard loop review."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Callable, Sequence

from flowguard.export import to_jsonable
from flowguard.loop import GraphEdge, LoopCheckConfig, LoopCheckReport, check_loops
from flowguard.progress import ProgressCheckConfig, ProgressCheckReport, check_progress


@dataclass(frozen=True)
class ReviewState:
    phase: str
    retry_count: int | str = 0
    rewrite_count: int | str = 0


TransitionFn = Callable[[ReviewState], tuple[GraphEdge, ...]]


@dataclass(frozen=True)
class LoopScenario:
    name: str
    description: str
    transition_fn: TransitionFn
    initial_state: ReviewState
    terminal_phases: tuple[str, ...]
    success_phases: tuple[str, ...] = ()
    required_success: bool = False
    expected_status: str = "ok"
    expected_findings: tuple[str, ...] = ()
    notes: str = ""


@dataclass(frozen=True)
class LoopReviewResult:
    scenario_name: str
    expected_summary: str
    observed_summary: str
    status: str
    evidence: tuple[str, ...]
    report: LoopCheckReport
    progress_report: ProgressCheckReport | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "scenario_name": self.scenario_name,
            "expected_summary": self.expected_summary,
            "observed_summary": self.observed_summary,
            "status": self.status,
            "evidence": list(self.evidence),
            "report": self.report.to_dict(),
            "progress_report": (
                self.progress_report.to_dict()
                if self.progress_report is not None
                else None
            ),
        }


@dataclass(frozen=True)
class LoopReviewReport:
    ok: bool
    total: int
    passed: int
    expected_violations_observed: int
    unexpected_violations: int
    missing_expected_violations: int
    needs_human_review: int
    known_limitations: int
    results: tuple[LoopReviewResult, ...]

    def format_text(self) -> str:
        lines = [
            "=== flowguard loop review ===",
            "",
            f"total: {self.total}",
            f"passed: {self.passed}",
            f"expected violations observed: {self.expected_violations_observed}",
            f"unexpected violations: {self.unexpected_violations}",
            f"missing expected violations: {self.missing_expected_violations}",
            f"needs human review: {self.needs_human_review}",
            f"known limitations: {self.known_limitations}",
            f"status: {'OK' if self.ok else 'MISMATCH'}",
        ]
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
        return "\n".join(lines)

    def to_dict(self) -> dict[str, object]:
        return {
            "ok": self.ok,
            "total": self.total,
            "passed": self.passed,
            "expected_violations_observed": self.expected_violations_observed,
            "unexpected_violations": self.unexpected_violations,
            "missing_expected_violations": self.missing_expected_violations,
            "needs_human_review": self.needs_human_review,
            "known_limitations": self.known_limitations,
            "results": [result.to_dict() for result in self.results],
        }

    def to_json_text(self, indent: int = 2) -> str:
        return json.dumps(to_jsonable(self.to_dict()), indent=indent, sort_keys=True)


def edge(old: ReviewState, new: ReviewState, label: str, reason: str = "") -> GraphEdge:
    return GraphEdge(old_state=old, new_state=new, label=label, reason=reason)


def by_phase(mapping: dict[str, Sequence[tuple[str, str]]]) -> TransitionFn:
    def transition(state: ReviewState) -> tuple[GraphEdge, ...]:
        transitions = mapping.get(state.phase, ())
        return tuple(
            edge(state, ReviewState(phase), label)
            for label, phase in transitions
        )

    return transition


def good_retry_limit_transition(state: ReviewState) -> tuple[GraphEdge, ...]:
    if state.phase == "new":
        return (edge(state, ReviewState("error", retry_count=0), "new_to_error"),)
    if state.phase == "error" and state.retry_count == 0:
        return (edge(state, ReviewState("retry", retry_count=1), "retry_1"),)
    if state.phase == "retry" and state.retry_count == 1:
        return (edge(state, ReviewState("error", retry_count=1), "retry_to_error_1"),)
    if state.phase == "error" and state.retry_count == 1:
        return (edge(state, ReviewState("retry", retry_count=2), "retry_2"),)
    if state.phase == "retry" and state.retry_count == 2:
        return (edge(state, ReviewState("needs_human", retry_count=2), "retry_limit"),)
    return ()


def _config(scenario: LoopScenario) -> LoopCheckConfig:
    terminal = set(scenario.terminal_phases)
    success = set(scenario.success_phases)
    return LoopCheckConfig(
        initial_states=(scenario.initial_state,),
        transition_fn=scenario.transition_fn,
        is_terminal=lambda state: state.phase in terminal,
        is_success=lambda state: state.phase in success,
        required_success=scenario.required_success,
    )


def _observed_findings(report: LoopCheckReport) -> tuple[str, ...]:
    findings: list[str] = []
    if report.stuck_states:
        findings.append("stuck_state")
    if report.non_terminating_components:
        findings.append("non_terminating_component")
    if report.unreachable_success:
        findings.append("unreachable_success")
    if report.terminal_with_outgoing_edges:
        findings.append("terminal_with_outgoing_edges")
    return tuple(findings)


def _progress_config(scenario: LoopScenario) -> ProgressCheckConfig:
    terminal = set(scenario.terminal_phases)
    success = set(scenario.success_phases)
    return ProgressCheckConfig(
        initial_states=(scenario.initial_state,),
        transition_fn=scenario.transition_fn,
        is_terminal=lambda state: state.phase in terminal,
        is_success=lambda state: state.phase in success,
    )


def review_loop_scenario(scenario: LoopScenario) -> LoopReviewResult:
    report = check_loops(_config(scenario))
    progress_report = check_progress(_progress_config(scenario))
    observed = tuple(dict.fromkeys(_observed_findings(report) + progress_report.finding_names()))
    expected = set(scenario.expected_findings)
    observed_set = set(observed)
    observed_has_violation = not report.ok or not progress_report.ok

    if scenario.expected_status == "known_limitation":
        status = "known_limitation"
    elif scenario.expected_status == "needs_human_review":
        status = "needs_human_review"
    elif scenario.expected_status == "violation":
        if not observed_has_violation:
            status = "missing_expected_violation"
        elif expected and not expected.issubset(observed_set):
            status = "missing_expected_violation"
        else:
            status = "expected_violation_observed"
    elif scenario.expected_status == "ok":
        status = "pass" if not observed_has_violation else "unexpected_violation"
    else:
        status = "needs_human_review"

    evidence = [
        f"observed findings: {observed or ('none',)}",
        f"states={report.graph_summary.get('states')}",
        f"edges={report.graph_summary.get('edges')}",
        f"progress_findings={progress_report.finding_names() or ('none',)}",
    ]
    if progress_report.findings:
        evidence.append(
            "progress states: "
            + repr(tuple(finding.states for finding in progress_report.findings[:3]))
        )
    if report.non_terminating_components:
        evidence.append(
            "bottom SCC: "
            + repr(tuple(component.states for component in report.non_terminating_components))
        )
    if report.stuck_states:
        evidence.append(f"stuck states: {report.stuck_states!r}")
    if report.terminal_with_outgoing_edges:
        evidence.append(
            "terminal outgoing: "
            + repr(tuple(item.state for item in report.terminal_with_outgoing_edges))
        )
    if scenario.notes:
        evidence.append(scenario.notes)

    return LoopReviewResult(
        scenario_name=scenario.name,
        expected_summary=f"{scenario.expected_status.upper()} {'/'.join(scenario.expected_findings)}",
        observed_summary=(
            "OK"
            if not observed_has_violation
            else "VIOLATION " + ",".join(observed)
        ),
        status=status,
        evidence=tuple(evidence),
        report=report,
        progress_report=progress_report,
    )


def run_loop_review(scenarios: Sequence[LoopScenario] | None = None) -> LoopReviewReport:
    results = tuple(review_loop_scenario(scenario) for scenario in (scenarios or all_loop_scenarios()))
    unexpected = sum(1 for result in results if result.status == "unexpected_violation")
    missing = sum(1 for result in results if result.status == "missing_expected_violation")
    ok = unexpected == 0 and missing == 0
    return LoopReviewReport(
        ok=ok,
        total=len(results),
        passed=sum(1 for result in results if result.status == "pass"),
        expected_violations_observed=sum(
            1 for result in results if result.status == "expected_violation_observed"
        ),
        unexpected_violations=unexpected,
        missing_expected_violations=missing,
        needs_human_review=sum(1 for result in results if result.status == "needs_human_review"),
        known_limitations=sum(1 for result in results if result.status == "known_limitation"),
        results=results,
    )


def all_loop_scenarios() -> tuple[LoopScenario, ...]:
    new = ReviewState("new")
    return (
        LoopScenario(
            "L01_good_rewrite_once_then_ready",
            "Bounded rewrite reaches done.",
            by_phase({
                "new": (("new_to_maybe", "maybe"),),
                "maybe": (("maybe_to_rewrite", "rewrite"),),
                "rewrite": (("rewrite_to_ready", "ready"),),
                "ready": (("ready_to_done", "done"),),
            }),
            new,
            terminal_phases=("done",),
            success_phases=("done",),
            required_success=True,
            expected_status="ok",
        ),
        LoopScenario(
            "L02_bad_infinite_rewrite_loop",
            "Rewrite cycles with maybe forever.",
            by_phase({
                "new": (("new_to_maybe", "maybe"),),
                "maybe": (("maybe_to_rewrite", "rewrite"),),
                "rewrite": (("rewrite_to_maybe", "maybe"),),
            }),
            new,
            terminal_phases=(),
            success_phases=("done",),
            required_success=True,
            expected_status="violation",
            expected_findings=("non_terminating_component", "unreachable_success"),
        ),
        LoopScenario(
            "L03_good_retry_limit_then_needs_human",
            "Retry is bounded and reaches human terminal.",
            good_retry_limit_transition,
            new,
            terminal_phases=("needs_human",),
            success_phases=("needs_human",),
            required_success=True,
            expected_status="ok",
        ),
        LoopScenario(
            "L04_bad_retry_no_limit",
            "Retry/error cycle has no terminal.",
            by_phase({
                "new": (("new_to_error", "error"),),
                "error": (("error_to_retry", "retry"),),
                "retry": (("retry_to_error", "error"),),
            }),
            new,
            terminal_phases=(),
            expected_status="violation",
            expected_findings=("non_terminating_component",),
        ),
        LoopScenario(
            "L05_bad_waiting_self_loop",
            "Waiting loops to itself.",
            by_phase({
                "new": (("new_to_waiting", "waiting"),),
                "waiting": (("waiting_to_waiting", "waiting"),),
            }),
            new,
            terminal_phases=(),
            expected_status="violation",
            expected_findings=("non_terminating_component",),
        ),
        LoopScenario(
            "L06_bad_nonterminal_dead_state",
            "Maybe has no outgoing edge and done is unreachable.",
            by_phase({"new": (("new_to_maybe", "maybe"),)}),
            new,
            terminal_phases=("done",),
            success_phases=("done",),
            required_success=True,
            expected_status="violation",
            expected_findings=("stuck_state", "unreachable_success"),
        ),
        LoopScenario(
            "L07_good_ask_human_terminal",
            "Needs human is acceptable terminal.",
            by_phase({
                "new": (("new_to_maybe", "maybe"),),
                "maybe": (("maybe_to_needs_human", "needs_human"),),
            }),
            new,
            terminal_phases=("needs_human",),
            success_phases=("needs_human",),
            required_success=True,
            expected_status="ok",
        ),
        LoopScenario(
            "L08_terminal_with_outgoing_edge",
            "Done still has outgoing transition.",
            by_phase({
                "new": (("new_to_done", "done"),),
                "done": (("done_to_maybe", "maybe"),),
                "maybe": (("maybe_to_done", "done"),),
            }),
            new,
            terminal_phases=("done",),
            success_phases=("done",),
            required_success=True,
            expected_status="violation",
            expected_findings=("terminal_with_outgoing_edges",),
        ),
        LoopScenario(
            "L09_unreachable_success",
            "Ignored terminal is reachable but applied success is not.",
            by_phase({
                "new": (("new_to_maybe", "maybe"),),
                "maybe": (("maybe_to_ignored", "ignored"),),
            }),
            new,
            terminal_phases=("ignored",),
            success_phases=("applied",),
            required_success=True,
            expected_status="violation",
            expected_findings=("unreachable_success",),
        ),
        LoopScenario(
            "L10_good_ignore_terminal_no_success_required",
            "Ignored terminal is acceptable when success is optional.",
            by_phase({
                "new": (("new_to_maybe", "maybe"),),
                "maybe": (("maybe_to_ignored", "ignored"),),
            }),
            new,
            terminal_phases=("ignored",),
            success_phases=("applied",),
            required_success=False,
            expected_status="ok",
        ),
        LoopScenario(
            "L11_bad_refresh_invalidate_cycle",
            "Refresh/invalidate/cache cycle has no terminal.",
            by_phase({
                "new": (("new_to_cached", "cached"),),
                "cached": (("cached_to_refresh", "refresh_requested"),),
                "refresh_requested": (("refresh_to_invalidated", "invalidated"),),
                "invalidated": (("invalidated_to_cached", "cached"),),
            }),
            new,
            terminal_phases=(),
            expected_status="violation",
            expected_findings=("non_terminating_component",),
        ),
        LoopScenario(
            "L12_good_refresh_then_done",
            "Refresh path reaches done.",
            by_phase({
                "new": (("new_to_cached", "cached"),),
                "cached": (("cached_to_refresh", "refresh_requested"),),
                "refresh_requested": (("refresh_to_updated", "updated"),),
                "updated": (("updated_to_done", "done"),),
            }),
            new,
            terminal_phases=("done",),
            success_phases=("done",),
            required_success=True,
            expected_status="ok",
        ),
        LoopScenario(
            "L13_bad_branch_has_one_good_one_bad_loop",
            "Maybe can go to done or loop through rewrite.",
            by_phase({
                "new": (("new_to_maybe", "maybe"),),
                "maybe": (("maybe_to_done", "done"), ("maybe_to_rewrite", "rewrite")),
                "rewrite": (("rewrite_to_maybe", "maybe"),),
            }),
            new,
            terminal_phases=("done",),
            success_phases=("done",),
            required_success=True,
            expected_status="violation",
            expected_findings=("potential_nontermination", "missing_progress_guarantee"),
            notes="Progress checking reports the escape-edge cycle because no ranking rule forces progress.",
        ),
        LoopScenario(
            "L14_bad_cycle_with_escape_but_no_forced_progress",
            "Cycle has escape to done but no progress fairness.",
            by_phase({
                "new": (("new_to_maybe", "maybe"),),
                "maybe": (("maybe_to_rewrite", "rewrite"), ("maybe_to_done", "done")),
                "rewrite": (("rewrite_to_maybe", "maybe"),),
            }),
            new,
            terminal_phases=("done",),
            success_phases=("done",),
            required_success=True,
            expected_status="violation",
            expected_findings=("potential_nontermination", "missing_progress_guarantee"),
            notes="Progress checking reports the cycle with escape because fairness/progress is not modeled.",
        ),
    )


__all__ = [
    "LoopReviewReport",
    "LoopReviewResult",
    "LoopScenario",
    "ReviewState",
    "all_loop_scenarios",
    "run_loop_review",
]
