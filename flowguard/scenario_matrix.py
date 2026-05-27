"""Small deterministic scenario matrix builder."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Sequence

from .scenario import Scenario, ScenarioExpectation


@dataclass(frozen=True)
class _StateEntry:
    state: Any
    tags: tuple[str, ...] = ()
    notes: str = ""


@dataclass(frozen=True)
class _ScenarioPattern:
    kind: str
    sequence: tuple[Any, ...]
    token: str
    description: str
    tags: tuple[str, ...]
    notes: str = ""


@dataclass(frozen=True)
class _ModelChallengeCandidate:
    kind: str
    sequence: tuple[Any, ...]
    initial_state: Any
    tags: tuple[str, ...]
    notes: str
    priority: int = 100


class ScenarioMatrixBuilder:
    """Build a small set of high-value deterministic scenarios."""

    def __init__(
        self,
        *,
        name_prefix: str,
        initial_states: Iterable[Any],
        inputs: Sequence[Any],
        workflow: Any = None,
        invariants: Sequence[Any] = (),
        expectation: ScenarioExpectation | None = None,
        max_sequence_length: int | None = None,
        max_scenarios: int = 20,
        tags: Sequence[str] = (),
        notes: str = "",
    ) -> None:
        self.name_prefix = str(name_prefix)
        self.inputs = tuple(inputs)
        self.workflow = workflow
        self.invariants = tuple(invariants)
        self.expectation = expectation
        self.max_sequence_length = max_sequence_length
        self.max_scenarios = int(max_scenarios)
        self.tags = tuple(tags)
        self.notes = str(notes or "")
        self._state_entries = [
            _StateEntry(state=state, tags=("initial_state",))
            for state in tuple(initial_states)
        ]
        self._patterns: list[_ScenarioPattern] = []
        self._seen_patterns: set[tuple[str, tuple[str, ...]]] = set()

    def special_initial_states(
        self,
        states: Iterable[Any],
        *,
        tag: str = "special_initial_state",
        notes: str = "",
    ) -> "ScenarioMatrixBuilder":
        """Add optional special or invalid initial states."""

        for state in states:
            self._state_entries.append(
                _StateEntry(state=state, tags=(tag,), notes=notes)
            )
        return self

    def single_inputs(self) -> "ScenarioMatrixBuilder":
        """Add one scenario for each single input."""

        for index, input_obj in enumerate(self.inputs):
            self._add_pattern(
                kind="single",
                sequence=(input_obj,),
                token=f"input{index + 1}",
                description=f"single input {index + 1}: {input_obj!r}",
                tags=("single_input",),
            )
        return self

    def repeat_same(self, max_repeats: int = 2) -> "ScenarioMatrixBuilder":
        """Add repeated-same-input scenarios up to `max_repeats`."""

        max_repeats = max(2, int(max_repeats))
        for repeat_count in range(2, max_repeats + 1):
            for index, input_obj in enumerate(self.inputs):
                self._add_pattern(
                    kind=f"repeat_same_{repeat_count}",
                    sequence=tuple(input_obj for _count in range(repeat_count)),
                    token=f"input{index + 1}x{repeat_count}",
                    description=f"input {index + 1} repeated {repeat_count} time(s): {input_obj!r}",
                    tags=("repeated_input", "repeat_same"),
                )
        return self

    def pairwise_orders(self) -> "ScenarioMatrixBuilder":
        """Add ordered pairs for every distinct pair of inputs."""

        for first_index, first in enumerate(self.inputs):
            for second_index, second in enumerate(self.inputs):
                if first_index == second_index:
                    continue
                self._add_pattern(
                    kind="pairwise_order",
                    sequence=(first, second),
                    token=f"input{first_index + 1}_then_input{second_index + 1}",
                    description=(
                        f"ordered pair input {first_index + 1} then "
                        f"input {second_index + 1}: {first!r}, {second!r}"
                    ),
                    tags=("pairwise_order",),
                )
        return self

    def aba(self) -> "ScenarioMatrixBuilder":
        """Add A-B-A repeat-after-different-input scenarios."""

        for first_index, first in enumerate(self.inputs):
            for second_index, second in enumerate(self.inputs):
                if first_index == second_index:
                    continue
                self._add_pattern(
                    kind="aba",
                    sequence=(first, second, first),
                    token=f"input{first_index + 1}_input{second_index + 1}_input{first_index + 1}",
                    description=(
                        f"ABA sequence input {first_index + 1}, "
                        f"input {second_index + 1}, input {first_index + 1}"
                    ),
                    tags=("aba", "repeated_input"),
                )
        return self

    def challenge_patterns(self) -> "ScenarioMatrixBuilder":
        """Add deterministic high-risk challenge routes.

        These routes are still ordinary generated scenarios. Without a supplied
        domain expectation, they stay `needs_human_review` like other generated
        matrix entries.
        """

        for index, input_obj in enumerate(self.inputs):
            self._add_pattern(
                kind="partial_failure_retry",
                sequence=(input_obj, input_obj),
                token=f"input{index + 1}",
                description=(
                    f"partial-failure retry challenge for input {index + 1}: "
                    f"{input_obj!r}"
                ),
                tags=(
                    "challenge",
                    "partial_failure_retry",
                    "repeated_input",
                    "candidate_evidence",
                ),
                notes=(
                    "challenge route: a side effect may have succeeded while "
                    "local state still invites a retry"
                ),
            )
            self._add_pattern(
                kind="duplicate_delivery",
                sequence=(input_obj, input_obj, input_obj),
                token=f"input{index + 1}x3",
                description=(
                    f"duplicate-delivery challenge for input {index + 1}: "
                    f"{input_obj!r}"
                ),
                tags=(
                    "challenge",
                    "duplicate_delivery",
                    "repeated_input",
                    "candidate_evidence",
                ),
                notes=(
                    "challenge route: repeated delivery should not duplicate "
                    "records, decisions, attempts, or side effects"
                ),
            )

        for first_index, first in enumerate(self.inputs):
            for second_index, second in enumerate(self.inputs):
                if first_index == second_index:
                    continue
                self._add_pattern(
                    kind="stale_state_after_change",
                    sequence=(first, second),
                    token=f"input{first_index + 1}_then_input{second_index + 1}",
                    description=(
                        f"stale-state challenge input {first_index + 1} then "
                        f"input {second_index + 1}: {first!r}, {second!r}"
                    ),
                    tags=(
                        "challenge",
                        "stale_state",
                        "source_of_truth_change",
                        "candidate_evidence",
                    ),
                    notes=(
                        "challenge route: derived state or cache may still "
                        "reflect an older source after a later input"
                    ),
                )
                self._add_pattern(
                    kind="delayed_replay",
                    sequence=(first, second, first),
                    token=f"input{first_index + 1}_input{second_index + 1}_input{first_index + 1}",
                    description=(
                        f"delayed-replay challenge input {first_index + 1}, "
                        f"input {second_index + 1}, input {first_index + 1}"
                    ),
                    tags=(
                        "challenge",
                        "delayed_replay",
                        "reordered_input",
                        "candidate_evidence",
                    ),
                    notes=(
                        "challenge route: an old input returns after a newer "
                        "state transition and must not revive stale obligations"
                    ),
                )
                self._add_pattern(
                    kind="terminal_replay",
                    sequence=(first, second, second),
                    token=f"input{first_index + 1}_input{second_index + 1}x2",
                    description=(
                        f"terminal-replay challenge input {first_index + 1}, "
                        f"input {second_index + 1} twice"
                    ),
                    tags=(
                        "challenge",
                        "terminal_replay",
                        "repeated_input",
                        "candidate_evidence",
                    ),
                    notes=(
                        "challenge route: a terminal or later-stage input is "
                        "replayed and must not reopen completed work"
                    ),
                )
        return self

    def build(self) -> tuple[Scenario, ...]:
        """Return scenarios compatible with the existing Scenario Sandbox."""

        if not self._state_entries:
            return ()
        scenarios: list[Scenario] = []
        multiple_states = len(self._state_entries) > 1
        for state_index, state_entry in enumerate(self._state_entries, start=1):
            for pattern in self._patterns:
                if len(scenarios) >= self.max_scenarios:
                    return tuple(scenarios)
                state_suffix = f"_state{state_index}" if multiple_states else ""
                notes = self._join_notes(self.notes, pattern.notes, state_entry.notes)
                scenarios.append(
                    Scenario(
                        name=f"{self.name_prefix}_{pattern.kind}_{pattern.token}{state_suffix}",
                        description=pattern.description,
                        initial_state=state_entry.state,
                        external_input_sequence=pattern.sequence,
                        expected=self._expectation(),
                        tags=self.tags + pattern.tags + state_entry.tags,
                        notes=notes,
                        workflow=self.workflow,
                        invariants=self.invariants,
                    )
                )
        return tuple(scenarios)

    def _add_pattern(
        self,
        *,
        kind: str,
        sequence: Sequence[Any],
        token: str,
        description: str,
        tags: Sequence[str],
        notes: str = "",
    ) -> None:
        sequence_tuple = tuple(sequence)
        if self.max_sequence_length is not None and len(sequence_tuple) > self.max_sequence_length:
            return
        signature = (kind, tuple(repr(item) for item in sequence_tuple))
        if signature in self._seen_patterns:
            return
        self._seen_patterns.add(signature)
        self._patterns.append(
            _ScenarioPattern(
                kind=kind,
                sequence=sequence_tuple,
                token=token,
                description=description,
                tags=tuple(tags),
                notes=notes,
            )
        )

    def _expectation(self) -> ScenarioExpectation:
        if self.expectation is not None:
            return self.expectation
        return ScenarioExpectation(
            expected_status="needs_human_review",
            summary="generated scenario; add a domain expectation before treating it as pass/fail",
        )

    @staticmethod
    def _join_notes(*notes: str) -> str:
        return " ".join(note for note in notes if note)


def synthesize_challenge_scenarios_from_report(
    *,
    name_prefix: str,
    report: Any,
    workflow: Any = None,
    invariants: Sequence[Any] = (),
    expectation: ScenarioExpectation | None = None,
    max_scenarios: int = 20,
    tags: Sequence[str] = (),
    notes: str = "",
) -> tuple[Scenario, ...]:
    """Synthesize candidate challenge scenarios from actual model evidence.

    The source is a FlowGuard check report, not a static input-shape matrix.
    Generated scenarios remain candidate evidence and default to
    `needs_human_review` until the caller supplies a domain expectation.
    """

    candidates = _model_challenge_candidates(report)
    if not candidates:
        return ()
    expectation = expectation or ScenarioExpectation(
        expected_status="needs_human_review",
        summary=(
            "model-derived challenge scenario; add a domain oracle, replay, "
            "or test before treating it as pass/fail evidence"
        ),
    )
    base_tags = tuple(tags)
    base_notes = str(notes or "")
    scenarios: list[Scenario] = []
    seen: set[tuple[str, tuple[str, ...], str]] = set()
    for candidate in candidates:
        if len(scenarios) >= max_scenarios:
            break
        signature = (
            repr(candidate.initial_state),
            tuple(repr(item) for item in candidate.sequence),
            candidate.kind,
        )
        if signature in seen:
            continue
        seen.add(signature)
        index = len(scenarios) + 1
        scenario_notes = ScenarioMatrixBuilder._join_notes(base_notes, candidate.notes)
        scenarios.append(
            Scenario(
                name=f"{name_prefix}_{candidate.kind}_{index}",
                description=(
                    f"model-derived {candidate.kind.replace('_', ' ')} challenge "
                    f"from explored FlowGuard trace"
                ),
                initial_state=candidate.initial_state,
                external_input_sequence=candidate.sequence,
                expected=expectation,
                tags=base_tags + candidate.tags,
                notes=scenario_notes,
                workflow=workflow,
                invariants=tuple(invariants),
            )
        )
    return tuple(scenarios)


def _model_challenge_candidates(report: Any) -> tuple[_ModelChallengeCandidate, ...]:
    candidates: list[_ModelChallengeCandidate] = []
    for index, violation in enumerate(tuple(getattr(report, "violations", ()) or ())):
        trace = getattr(violation, "trace", None)
        sequence = _trace_sequence(trace)
        if not sequence:
            continue
        invariant_name = str(getattr(violation, "invariant_name", "invariant"))
        candidates.append(
            _ModelChallengeCandidate(
                kind="model_counterexample",
                sequence=sequence,
                initial_state=_trace_initial_state(trace),
                tags=(
                    "challenge",
                    "model_derived",
                    "model_counterexample",
                    "candidate_evidence",
                ),
                notes=(
                    "model-derived challenge route: Explorer found invariant "
                    f"{invariant_name!r} violation on this exact sequence"
                ),
                priority=index,
            )
        )

    base_priority = len(candidates) + 10
    for index, dead in enumerate(tuple(getattr(report, "dead_branches", ()) or ())):
        trace = getattr(dead, "trace", None)
        sequence = _trace_sequence(trace)
        if not sequence:
            continue
        function_name = str(getattr(dead, "function_name", "") or "workflow")
        reason = str(getattr(dead, "reason", "") or "dead branch")
        candidates.append(
            _ModelChallengeCandidate(
                kind="model_dead_branch",
                sequence=sequence,
                initial_state=_trace_initial_state(trace),
                tags=("challenge", "model_derived", "dead_branch", "candidate_evidence"),
                notes=(
                    "model-derived challenge route: Explorer reached dead branch "
                    f"in {function_name!r}: {reason}"
                ),
                priority=base_priority + index,
            )
        )

    base_priority = len(candidates) + 20
    for index, exc in enumerate(tuple(getattr(report, "exception_branches", ()) or ())):
        trace = getattr(exc, "trace", None)
        sequence = _trace_sequence(trace)
        if not sequence:
            continue
        function_name = str(getattr(exc, "function_name", "") or "workflow")
        error_type = str(getattr(exc, "error_type", "") or "Exception")
        candidates.append(
            _ModelChallengeCandidate(
                kind="model_exception_branch",
                sequence=sequence,
                initial_state=_trace_initial_state(trace),
                tags=("challenge", "model_derived", "exception_branch", "candidate_evidence"),
                notes=(
                    "model-derived challenge route: Explorer reached exception "
                    f"{error_type} in {function_name!r}"
                ),
                priority=base_priority + index,
            )
        )

    base_priority = len(candidates) + 30
    for index, trace in enumerate(tuple(getattr(report, "traces", ()) or ())):
        candidates.extend(_trace_semantic_candidates(trace, base_priority + index * 10))

    return tuple(sorted(candidates, key=lambda item: item.priority))


def _trace_semantic_candidates(trace: Any, priority: int) -> tuple[_ModelChallengeCandidate, ...]:
    sequence = _trace_sequence(trace)
    if not sequence:
        return ()
    candidates: list[_ModelChallengeCandidate] = []
    labels = tuple(label for label in getattr(trace, "labels", ()) if label)
    repeated_label = _first_repeated(labels)
    if repeated_label:
        candidates.append(
            _ModelChallengeCandidate(
                kind="model_repeated_label",
                sequence=sequence,
                initial_state=_trace_initial_state(trace),
                tags=("challenge", "model_derived", "repeated_label", "candidate_evidence"),
                notes=(
                    "model-derived challenge route: trace repeats label "
                    f"{repeated_label!r}, which can expose duplicate side effects "
                    "or missing idempotency"
                ),
                priority=priority,
            )
        )

    block_names = tuple(str(getattr(step, "function_name", "")) for step in getattr(trace, "steps", ()))
    repeated_block = _first_repeated(tuple(name for name in block_names if name))
    if repeated_block:
        candidates.append(
            _ModelChallengeCandidate(
                kind="model_repeated_block",
                sequence=sequence,
                initial_state=_trace_initial_state(trace),
                tags=("challenge", "model_derived", "repeated_block", "candidate_evidence"),
                notes=(
                    "model-derived challenge route: trace re-enters block "
                    f"{repeated_block!r}, so retry/replay behavior should be checked"
                ),
                priority=priority + 1,
            )
        )

    if _has_interleaved_repeat(sequence):
        candidates.append(
            _ModelChallengeCandidate(
                kind="model_interleaved_replay",
                sequence=sequence,
                initial_state=_trace_initial_state(trace),
                tags=("challenge", "model_derived", "interleaved_replay", "candidate_evidence"),
                notes=(
                    "model-derived challenge route: an earlier external input "
                    "returns after a different transition in the explored trace"
                ),
                priority=priority + 2,
            )
        )

    repeated_state = _first_repeated(_state_reprs(trace))
    if repeated_state:
        candidates.append(
            _ModelChallengeCandidate(
                kind="model_state_revisit",
                sequence=sequence,
                initial_state=_trace_initial_state(trace),
                tags=("challenge", "model_derived", "state_revisit", "candidate_evidence"),
                notes=(
                    "model-derived challenge route: explored trace revisits an "
                    "abstract state, which can hide loops, stale evidence, or "
                    "terminal replay"
                ),
                priority=priority + 3,
            )
        )

    risk_family = _risk_family_from_trace(trace)
    if risk_family:
        candidates.append(
            _ModelChallengeCandidate(
                kind=f"model_{risk_family}_risk",
                sequence=sequence,
                initial_state=_trace_initial_state(trace),
                tags=("challenge", "model_derived", risk_family, "candidate_evidence"),
                notes=(
                    "model-derived challenge route: trace labels, blocks, or "
                    f"reasons mention {risk_family!r} risk signals"
                ),
                priority=priority + 4,
            )
        )
    return tuple(candidates)


def _trace_sequence(trace: Any) -> tuple[Any, ...]:
    if trace is None:
        return ()
    return tuple(getattr(trace, "external_inputs", ()) or ())


def _trace_initial_state(trace: Any) -> Any:
    return getattr(trace, "initial_state", None)


def _first_repeated(items: Sequence[Any]) -> Any | None:
    seen: set[Any] = set()
    for item in items:
        if item in seen:
            return item
        seen.add(item)
    return None


def _has_interleaved_repeat(sequence: Sequence[Any]) -> bool:
    for first_index, first in enumerate(sequence):
        for second_index in range(first_index + 2, len(sequence)):
            if sequence[second_index] == first:
                return True
    return False


def _state_reprs(trace: Any) -> tuple[str, ...]:
    states = [repr(getattr(trace, "initial_state", None))]
    for step in getattr(trace, "steps", ()):
        states.append(repr(getattr(step, "new_state", None)))
    return tuple(states)


def _risk_family_from_trace(trace: Any) -> str:
    haystack = " ".join(
        " ".join(
            str(getattr(step, attr, ""))
            for attr in ("function_name", "label", "reason")
        )
        for step in getattr(trace, "steps", ())
    ).lower()
    families = (
        ("cache", ("cache", "stale", "source", "refresh", "materialized")),
        ("retry", ("retry", "timeout", "attempt", "late", "replay", "ack")),
        ("duplicate", ("duplicate", "dedup", "already", "repeat", "idempot")),
        ("side_effect", ("side_effect", "side effect", "effect", "send", "emit")),
        ("terminal", ("terminal", "final", "closed", "complete", "done")),
    )
    for family, keywords in families:
        if any(keyword in haystack for keyword in keywords):
            return family
    return ""


__all__ = ["ScenarioMatrixBuilder", "synthesize_challenge_scenarios_from_report"]
