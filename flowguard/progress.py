"""Progress, fairness, and bounded-temporal checks for finite state graphs."""

from __future__ import annotations

import json
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Sequence

from .core import FrozenMetadata, freeze_metadata
from .export import to_jsonable
from .loop import GraphEdge, LoopCheckConfig, StatePredicate, TransitionFn, build_reachable_graph, tarjan_scc


RankingFn = Callable[[Any], int | float]


@dataclass(frozen=True)
class EventuallyProperty:
    """Trace obligation over reachable graph states."""

    name: str
    trigger: StatePredicate
    target: StatePredicate
    description: str = ""


@dataclass(frozen=True)
class BoundedEventuallyProperty(EventuallyProperty):
    """Eventually property with a finite path-length bound."""

    max_steps: int = 1


@dataclass(frozen=True)
class ProgressFinding:
    """One actionable progress/fairness finding."""

    name: str
    message: str
    states: tuple[Any, ...] = ()
    edges: tuple[GraphEdge, ...] = ()
    metadata: FrozenMetadata = field(default_factory=tuple, compare=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "name", str(self.name))
        object.__setattr__(self, "message", str(self.message))
        object.__setattr__(self, "states", tuple(self.states))
        object.__setattr__(self, "edges", tuple(self.edges))
        object.__setattr__(self, "metadata", freeze_metadata(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "message": self.message,
            "states": to_jsonable(self.states),
            "edges": [edge.to_dict() for edge in self.edges],
            "metadata": to_jsonable(self.metadata),
        }


@dataclass(frozen=True)
class ProgressCheckConfig:
    """Configuration for pragmatic progress/fairness checks."""

    initial_states: tuple[Any, ...]
    transition_fn: TransitionFn
    is_terminal: StatePredicate
    is_success: StatePredicate | None = None
    ranking_fn: RankingFn | None = None
    eventually: tuple[EventuallyProperty, ...] = ()
    bounded_eventually: tuple[BoundedEventuallyProperty, ...] = ()
    max_states: int | None = None
    max_depth: int | None = None

    def __init__(
        self,
        initial_states: Sequence[Any],
        transition_fn: TransitionFn,
        is_terminal: StatePredicate,
        is_success: StatePredicate | None = None,
        ranking_fn: RankingFn | None = None,
        eventually: Sequence[EventuallyProperty] = (),
        bounded_eventually: Sequence[BoundedEventuallyProperty] = (),
        max_states: int | None = None,
        max_depth: int | None = None,
    ) -> None:
        object.__setattr__(self, "initial_states", tuple(initial_states))
        object.__setattr__(self, "transition_fn", transition_fn)
        object.__setattr__(self, "is_terminal", is_terminal)
        object.__setattr__(self, "is_success", is_success)
        object.__setattr__(self, "ranking_fn", ranking_fn)
        object.__setattr__(self, "eventually", tuple(eventually))
        object.__setattr__(self, "bounded_eventually", tuple(bounded_eventually))
        object.__setattr__(self, "max_states", max_states)
        object.__setattr__(self, "max_depth", max_depth)


@dataclass(frozen=True)
class ProgressCheckReport:
    """Structured progress/fairness report."""

    ok: bool
    findings: tuple[ProgressFinding, ...]
    graph_summary: dict[str, Any]
    reachable_states: tuple[Any, ...]
    edges: tuple[GraphEdge, ...]
    sccs: tuple[tuple[Any, ...], ...]

    def finding_names(self) -> tuple[str, ...]:
        return tuple(finding.name for finding in self.findings)

    def format_text(self, max_examples: int = 5) -> str:
        lines = [
            f"status: {'OK' if self.ok else 'VIOLATION'}",
            f"states: {self.graph_summary.get('states', 0)}",
            f"edges: {self.graph_summary.get('edges', 0)}",
            f"findings: {len(self.findings)}",
        ]
        for finding in self.findings[:max_examples]:
            lines.extend(
                [
                    "",
                    f"finding: {finding.name}",
                    f"message: {finding.message}",
                    f"states: {finding.states!r}",
                ]
            )
        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "findings": [finding.to_dict() for finding in self.findings],
            "graph_summary": to_jsonable(self.graph_summary),
            "reachable_states": to_jsonable(self.reachable_states),
            "edges": [edge.to_dict() for edge in self.edges],
            "sccs": to_jsonable(self.sccs),
        }

    def to_json_text(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, sort_keys=True)


def _adjacency(states: Sequence[Any], edges: Sequence[GraphEdge]) -> dict[Any, tuple[GraphEdge, ...]]:
    grouped: dict[Any, list[GraphEdge]] = {state: [] for state in states}
    for edge in edges:
        grouped.setdefault(edge.old_state, []).append(edge)
        grouped.setdefault(edge.new_state, grouped.get(edge.new_state, []))
    return {state: tuple(items) for state, items in grouped.items()}


def _component_is_cyclic(component: Sequence[Any], edges: Sequence[GraphEdge]) -> bool:
    component_set = set(component)
    if len(component_set) > 1:
        return True
    return any(edge.old_state in component_set and edge.new_state in component_set for edge in edges)


def _has_ranking_progress(component_edges: Sequence[GraphEdge], ranking_fn: RankingFn | None) -> bool:
    if ranking_fn is None:
        return False
    progressed = False
    for edge in component_edges:
        try:
            old_rank = ranking_fn(edge.old_state)
            new_rank = ranking_fn(edge.new_state)
        except Exception:
            return False
        if new_rank < old_rank:
            progressed = True
        elif new_rank > old_rank:
            return False
    return progressed


def _can_reach_target(
    start: Any,
    adjacency: dict[Any, tuple[GraphEdge, ...]],
    target: StatePredicate,
    max_steps: int | None = None,
) -> bool:
    queue: deque[tuple[Any, int]] = deque([(start, 0)])
    seen: set[Any] = {start}
    while queue:
        state, depth = queue.popleft()
        if target(state):
            return True
        if max_steps is not None and depth >= max_steps:
            continue
        for edge in adjacency.get(state, ()):
            if edge.new_state in seen:
                continue
            seen.add(edge.new_state)
            queue.append((edge.new_state, depth + 1))
    return False


def check_progress(config: ProgressCheckConfig) -> ProgressCheckReport:
    """Check pragmatic progress properties on the finite reachable graph."""

    loop_config = LoopCheckConfig(
        initial_states=config.initial_states,
        transition_fn=config.transition_fn,
        is_terminal=config.is_terminal,
        is_success=config.is_success,
        max_states=config.max_states,
        max_depth=config.max_depth,
        required_success=False,
        report_terminal_outgoing=False,
    )
    states, edges = build_reachable_graph(loop_config)
    sccs = tarjan_scc(states, edges)
    adjacency = _adjacency(states, edges)
    is_success = config.is_success or (lambda _state: False)
    findings: list[ProgressFinding] = []

    for component in sccs:
        component_set = set(component)
        if not _component_is_cyclic(component, edges):
            continue
        if any(config.is_terminal(state) or is_success(state) for state in component):
            continue

        internal_edges = tuple(
            edge
            for edge in edges
            if edge.old_state in component_set and edge.new_state in component_set
        )
        outgoing_edges = tuple(
            edge
            for edge in edges
            if edge.old_state in component_set and edge.new_state not in component_set
        )
        escape_edges = tuple(
            edge
            for edge in outgoing_edges
            if _can_reach_target(edge.new_state, adjacency, lambda state: config.is_terminal(state) or is_success(state))
        )
        if not escape_edges:
            continue

        if not _has_ranking_progress(internal_edges, config.ranking_fn):
            findings.append(
                ProgressFinding(
                    name="potential_nontermination",
                    message="cycle has an escape edge but can remain in the cycle without a ranking decrease",
                    states=tuple(component),
                    edges=internal_edges + escape_edges,
                    metadata={"escape_edges": len(escape_edges)},
                )
            )
            findings.append(
                ProgressFinding(
                    name="missing_progress_guarantee",
                    message="no bounded progress or ranking rule forces the escape edge to be taken",
                    states=tuple(component),
                    edges=internal_edges,
                    metadata={"internal_edges": len(internal_edges)},
                )
            )

    for prop in config.eventually:
        for state in states:
            if prop.trigger(state) and not _can_reach_target(state, adjacency, prop.target):
                findings.append(
                    ProgressFinding(
                        name=prop.name,
                        message=prop.description or "eventually target is not reachable from trigger state",
                        states=(state,),
                        metadata={"property": prop.name},
                    )
                )

    for prop in config.bounded_eventually:
        for state in states:
            if prop.trigger(state) and not _can_reach_target(state, adjacency, prop.target, prop.max_steps):
                findings.append(
                    ProgressFinding(
                        name=prop.name,
                        message=prop.description or f"target is not reachable within {prop.max_steps} steps",
                        states=(state,),
                        metadata={"property": prop.name, "max_steps": prop.max_steps},
                    )
                )

    return ProgressCheckReport(
        ok=not findings,
        findings=tuple(findings),
        graph_summary={"states": len(states), "edges": len(edges), "sccs": len(sccs)},
        reachable_states=states,
        edges=edges,
        sccs=sccs,
    )


__all__ = [
    "BoundedEventuallyProperty",
    "EventuallyProperty",
    "ProgressCheckConfig",
    "ProgressCheckReport",
    "ProgressFinding",
    "RankingFn",
    "check_progress",
]
