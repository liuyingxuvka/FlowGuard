"""Conformance replay for abstract flowguard traces."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Callable, Sequence

from .core import FrozenMetadata, InvariantResult, freeze_metadata
from .export import to_jsonable, trace_step_to_dict, trace_to_dict
from .replay import ReplayObservation, coerce_observation
from .trace import Trace, TraceStep


RuleCheck = Callable[[TraceStep, ReplayObservation], str | None]


@dataclass(frozen=True)
class ConformanceRule:
    """One comparison rule between an expected trace step and observation."""

    name: str
    description: str
    check: RuleCheck

    def evaluate(self, expected_step: TraceStep, observed_step: ReplayObservation) -> str | None:
        return self.check(expected_step, observed_step)


@dataclass(frozen=True)
class ConformanceViolation:
    """A mismatch between abstract model trace and production replay."""

    message: str
    step_index: int
    expected_step: TraceStep | None = None
    observed_step: ReplayObservation | None = None
    rule_name: str = ""
    trace: Trace | None = None
    metadata: FrozenMetadata = field(default_factory=tuple, compare=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "metadata", freeze_metadata(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "message": self.message,
            "step_index": self.step_index,
            "rule_name": self.rule_name,
            "expected_step": (
                trace_step_to_dict(self.expected_step)
                if self.expected_step is not None
                else None
            ),
            "observed_step": (
                self.observed_step.to_dict()
                if self.observed_step is not None
                else None
            ),
            "trace": trace_to_dict(self.trace) if self.trace is not None else None,
            "metadata": to_jsonable(self.metadata),
        }


@dataclass(frozen=True)
class ConformanceReport:
    """Structured result of replaying a trace against an implementation."""

    ok: bool
    violations: tuple[ConformanceViolation, ...] = ()
    replayed_steps: tuple[ReplayObservation, ...] = ()
    failed_step_index: int | None = None
    expected_trace: Trace | None = None
    summary: str = ""

    def format_text(self, max_examples: int = 3) -> str:
        lines = [
            f"status: {'OK' if self.ok else 'VIOLATION'}",
            self.summary or f"replayed_steps={len(self.replayed_steps)}",
            f"violations: {len(self.violations)}",
        ]
        for violation in self.violations[:max_examples]:
            lines.extend(
                [
                    "",
                    f"step: {violation.step_index}",
                    f"rule: {violation.rule_name or '(replay)'}",
                    f"message: {violation.message}",
                ]
            )
            if violation.expected_step is not None:
                lines.append(f"expected: {violation.expected_step!r}")
            if violation.observed_step is not None:
                lines.append(f"observed: {violation.observed_step!r}")
            if violation.trace is not None:
                lines.extend(["counterexample:", violation.trace.format_text()])
        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "summary": self.summary,
            "failed_step_index": self.failed_step_index,
            "replayed_steps": [step.to_dict() for step in self.replayed_steps],
            "violations": [violation.to_dict() for violation in self.violations],
            "expected_trace": (
                trace_to_dict(self.expected_trace)
                if self.expected_trace is not None
                else None
            ),
        }

    def to_json_text(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, sort_keys=True)


def projected_state_matches() -> ConformanceRule:
    def check(expected_step: TraceStep, observed_step: ReplayObservation) -> str | None:
        if observed_step.observed_state == expected_step.new_state:
            return None
        return (
            "projected state mismatch: "
            f"expected {expected_step.new_state!r}, "
            f"observed {observed_step.observed_state!r}"
        )

    return ConformanceRule(
        name="projected_state_matches",
        description="Adapter-projected production state equals expected abstract new_state.",
        check=check,
    )


def projected_output_matches() -> ConformanceRule:
    def check(expected_step: TraceStep, observed_step: ReplayObservation) -> str | None:
        if observed_step.observed_output == expected_step.function_output:
            return None
        return (
            "projected output mismatch: "
            f"expected {expected_step.function_output!r}, "
            f"observed {observed_step.observed_output!r}"
        )

    return ConformanceRule(
        name="projected_output_matches",
        description="Adapter-projected production output equals expected abstract output.",
        check=check,
    )


def label_matches() -> ConformanceRule:
    def check(expected_step: TraceStep, observed_step: ReplayObservation) -> str | None:
        if observed_step.label == expected_step.label:
            return None
        return (
            "label mismatch: "
            f"expected {expected_step.label!r}, observed {observed_step.label!r}"
        )

    return ConformanceRule(
        name="label_matches",
        description="Observed replay label equals expected trace label.",
        check=check,
    )


def default_conformance_rules() -> tuple[ConformanceRule, ...]:
    return (
        projected_state_matches(),
        projected_output_matches(),
        label_matches(),
    )


def _invariant_name(invariant: Any) -> str:
    return str(getattr(invariant, "name", getattr(invariant, "__name__", type(invariant).__name__)))


def _check_invariant(invariant: Any, state: Any, trace: Trace) -> InvariantResult:
    check = getattr(invariant, "check", None)
    try:
        result = check(state, trace) if check is not None else invariant(state, trace)
    except Exception as exc:
        return InvariantResult.fail(f"invariant raised {type(exc).__name__}: {exc}")
    if isinstance(result, InvariantResult):
        return result
    if bool(result):
        return InvariantResult.pass_()
    return InvariantResult.fail(f"invariant failed: {_invariant_name(invariant)}")


def replay_trace(
    trace: Trace,
    adapter: Any,
    rules: Sequence[ConformanceRule] | None = None,
    invariants: Sequence[Any] = (),
) -> ConformanceReport:
    """Replay one abstract trace against a production adapter."""

    active_rules = tuple(rules) if rules is not None else default_conformance_rules()
    replayed_steps: list[ReplayObservation] = []
    violations: list[ConformanceViolation] = []

    try:
        adapter.reset(trace.initial_state)
    except Exception as exc:
        violation = ConformanceViolation(
            message=f"adapter reset raised {type(exc).__name__}: {exc}",
            step_index=0,
            rule_name="adapter_reset",
            trace=trace,
        )
        return ConformanceReport(
            ok=False,
            violations=(violation,),
            failed_step_index=0,
            expected_trace=trace,
            summary="adapter reset failed",
        )

    for index, expected_step in enumerate(trace.steps, start=1):
        try:
            raw_observation = adapter.apply_step(expected_step)
            observation = coerce_observation(raw_observation, expected_step, adapter)
        except Exception as exc:
            violation = ConformanceViolation(
                message=f"adapter step raised {type(exc).__name__}: {exc}",
                step_index=index,
                expected_step=expected_step,
                rule_name="adapter_exception",
                trace=trace,
            )
            violations.append(violation)
            break

        replayed_steps.append(observation)

        for invariant in invariants:
            result = _check_invariant(invariant, observation.observed_state, trace)
            if not result.ok:
                violations.append(
                    ConformanceViolation(
                        message=result.message,
                        step_index=index,
                        expected_step=expected_step,
                        observed_step=observation,
                        rule_name=f"invariant:{_invariant_name(invariant)}",
                        trace=trace,
                        metadata=result.metadata,
                    )
                )
                break
        if violations:
            break

        for rule in active_rules:
            message = rule.evaluate(expected_step, observation)
            if message is None:
                continue
            violations.append(
                ConformanceViolation(
                    message=message,
                    step_index=index,
                    expected_step=expected_step,
                    observed_step=observation,
                    rule_name=rule.name,
                    trace=trace,
                )
            )
            break
        if violations:
            break

    failed_step_index = violations[0].step_index if violations else None
    return ConformanceReport(
        ok=not violations,
        violations=tuple(violations),
        replayed_steps=tuple(replayed_steps),
        failed_step_index=failed_step_index,
        expected_trace=trace,
        summary=f"replayed_steps={len(replayed_steps)}",
    )


__all__ = [
    "ConformanceReport",
    "ConformanceRule",
    "ConformanceViolation",
    "default_conformance_rules",
    "label_matches",
    "projected_output_matches",
    "projected_state_matches",
    "replay_trace",
]
