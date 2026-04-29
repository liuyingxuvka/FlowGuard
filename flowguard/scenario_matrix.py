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


__all__ = ["ScenarioMatrixBuilder"]
