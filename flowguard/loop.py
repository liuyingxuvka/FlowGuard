"""Reachable graph, SCC, and stuck-state checks."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Mapping, Sequence

from .core import FrozenMetadata, freeze_metadata
from .export import to_jsonable


TransitionFn = Callable[[Any], Iterable["GraphEdge | tuple[str, Any]"]]
StatePredicate = Callable[[Any], bool]


@dataclass(frozen=True)
class GraphEdge:
    """One transition in a reachable state graph."""

    old_state: Any
    new_state: Any
    label: str
    reason: str = ""
    metadata: FrozenMetadata = field(default_factory=tuple, compare=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "label", str(self.label))
        object.__setattr__(self, "reason", str(self.reason or ""))
        object.__setattr__(self, "metadata", freeze_metadata(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "old_state": to_jsonable(self.old_state),
            "new_state": to_jsonable(self.new_state),
            "label": self.label,
            "reason": self.reason,
            "metadata": to_jsonable(self.metadata),
        }


@dataclass(frozen=True)
class LoopCheckConfig:
    """Configuration for finite loop/stuck-state checks."""

    initial_states: tuple[Any, ...]
    transition_fn: TransitionFn
    is_terminal: StatePredicate
    is_success: StatePredicate | None = None
    max_states: int | None = None
    max_depth: int | None = None
    required_success: bool = False
    report_terminal_outgoing: bool = True

    def __init__(
        self,
        initial_states: Sequence[Any],
        transition_fn: TransitionFn,
        is_terminal: StatePredicate,
        is_success: StatePredicate | None = None,
        max_states: int | None = None,
        max_depth: int | None = None,
        required_success: bool = False,
        report_terminal_outgoing: bool = True,
    ) -> None:
        object.__setattr__(self, "initial_states", tuple(initial_states))
        object.__setattr__(self, "transition_fn", transition_fn)
        object.__setattr__(self, "is_terminal", is_terminal)
        object.__setattr__(self, "is_success", is_success)
        object.__setattr__(self, "max_states", max_states)
        object.__setattr__(self, "max_depth", max_depth)
        object.__setattr__(self, "required_success", required_success)
        object.__setattr__(self, "report_terminal_outgoing", report_terminal_outgoing)


@dataclass(frozen=True)
class NonTerminatingComponent:
    states: tuple[Any, ...]
    reason: str
    outgoing_edges: tuple[GraphEdge, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "states": to_jsonable(self.states),
            "reason": self.reason,
            "outgoing_edges": [edge.to_dict() for edge in self.outgoing_edges],
        }


@dataclass(frozen=True)
class TerminalOutgoing:
    state: Any
    outgoing_edges: tuple[GraphEdge, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "state": to_jsonable(self.state),
            "outgoing_edges": [edge.to_dict() for edge in self.outgoing_edges],
        }


@dataclass(frozen=True)
class LoopCheckReport:
    ok: bool
    stuck_states: tuple[Any, ...]
    non_terminating_components: tuple[NonTerminatingComponent, ...]
    unreachable_success: bool
    terminal_with_outgoing_edges: tuple[TerminalOutgoing, ...]
    graph_summary: Mapping[str, Any]
    reachable_states: tuple[Any, ...]
    edges: tuple[GraphEdge, ...]
    sccs: tuple[tuple[Any, ...], ...]
    bottom_sccs: tuple[tuple[Any, ...], ...]

    def format_text(self) -> str:
        lines = [
            f"status: {'OK' if self.ok else 'VIOLATION'}",
            f"states: {self.graph_summary.get('states', 0)}",
            f"edges: {self.graph_summary.get('edges', 0)}",
            f"stuck_states: {len(self.stuck_states)}",
            f"non_terminating_components: {len(self.non_terminating_components)}",
            f"unreachable_success: {self.unreachable_success}",
            f"terminal_with_outgoing_edges: {len(self.terminal_with_outgoing_edges)}",
        ]
        for state in self.stuck_states[:3]:
            lines.extend(["", f"stuck_state: {state!r}"])
        for component in self.non_terminating_components[:3]:
            lines.extend(
                [
                    "",
                    "non_terminating_component:",
                    f"states: {component.states!r}",
                    f"reason: {component.reason}",
                ]
            )
        for item in self.terminal_with_outgoing_edges[:3]:
            lines.extend(
                [
                    "",
                    f"terminal_with_outgoing: {item.state!r}",
                    f"edges: {tuple(edge.label for edge in item.outgoing_edges)!r}",
                ]
            )
        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "stuck_states": to_jsonable(self.stuck_states),
            "non_terminating_components": [
                component.to_dict() for component in self.non_terminating_components
            ],
            "unreachable_success": self.unreachable_success,
            "terminal_with_outgoing_edges": [
                item.to_dict() for item in self.terminal_with_outgoing_edges
            ],
            "graph_summary": to_jsonable(dict(self.graph_summary)),
            "reachable_states": to_jsonable(self.reachable_states),
            "edges": [edge.to_dict() for edge in self.edges],
            "sccs": to_jsonable(self.sccs),
            "bottom_sccs": to_jsonable(self.bottom_sccs),
        }

    def to_json_text(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, sort_keys=True)


def _coerce_edge(state: Any, raw: GraphEdge | tuple[str, Any]) -> GraphEdge:
    if isinstance(raw, GraphEdge):
        return raw
    label, new_state = raw
    return GraphEdge(old_state=state, new_state=new_state, label=label)


def build_reachable_graph(config: LoopCheckConfig) -> tuple[tuple[Any, ...], tuple[GraphEdge, ...]]:
    seen: set[Any] = set(config.initial_states)
    queue: list[tuple[Any, int]] = [(state, 0) for state in config.initial_states]
    states: list[Any] = list(config.initial_states)
    edges: list[GraphEdge] = []

    while queue:
        state, depth = queue.pop(0)
        if config.max_depth is not None and depth >= config.max_depth:
            continue

        raw_edges = tuple(config.transition_fn(state))
        for raw_edge in raw_edges:
            edge = _coerce_edge(state, raw_edge)
            edges.append(edge)
            if edge.new_state not in seen:
                seen.add(edge.new_state)
                states.append(edge.new_state)
                if config.max_states is not None and len(states) > config.max_states:
                    raise RuntimeError(f"max_states exceeded: {config.max_states}")
                queue.append((edge.new_state, depth + 1))

    return tuple(states), tuple(edges)


def tarjan_scc(states: Sequence[Any], edges: Sequence[GraphEdge]) -> tuple[tuple[Any, ...], ...]:
    adjacency: dict[Any, list[Any]] = {state: [] for state in states}
    for edge in edges:
        adjacency.setdefault(edge.old_state, []).append(edge.new_state)
        adjacency.setdefault(edge.new_state, [])

    index = 0
    stack: list[Any] = []
    on_stack: set[Any] = set()
    indices: dict[Any, int] = {}
    lowlinks: dict[Any, int] = {}
    components: list[tuple[Any, ...]] = []

    def strongconnect(state: Any) -> None:
        nonlocal index
        indices[state] = index
        lowlinks[state] = index
        index += 1
        stack.append(state)
        on_stack.add(state)

        for successor in adjacency.get(state, ()):
            if successor not in indices:
                strongconnect(successor)
                lowlinks[state] = min(lowlinks[state], lowlinks[successor])
            elif successor in on_stack:
                lowlinks[state] = min(lowlinks[state], indices[successor])

        if lowlinks[state] == indices[state]:
            component: list[Any] = []
            while True:
                node = stack.pop()
                on_stack.remove(node)
                component.append(node)
                if node == state:
                    break
            components.append(tuple(component))

    for state in states:
        if state not in indices:
            strongconnect(state)

    return tuple(components)


def bottom_sccs(sccs: Sequence[Sequence[Any]], edges: Sequence[GraphEdge]) -> tuple[tuple[Any, ...], ...]:
    bottoms: list[tuple[Any, ...]] = []
    for component in sccs:
        component_tuple = tuple(component)
        component_set = set(component_tuple)
        has_outgoing = any(
            edge.old_state in component_set and edge.new_state not in component_set
            for edge in edges
        )
        if not has_outgoing:
            bottoms.append(component_tuple)
    return tuple(bottoms)


def check_loops(config: LoopCheckConfig) -> LoopCheckReport:
    states, edges = build_reachable_graph(config)
    outgoing: dict[Any, list[GraphEdge]] = {state: [] for state in states}
    for edge in edges:
        outgoing.setdefault(edge.old_state, []).append(edge)
        outgoing.setdefault(edge.new_state, outgoing.get(edge.new_state, []))

    stuck_states = tuple(
        state
        for state in states
        if not config.is_terminal(state) and not outgoing.get(state)
    )

    terminal_outgoing = ()
    if config.report_terminal_outgoing:
        terminal_outgoing = tuple(
            TerminalOutgoing(state=state, outgoing_edges=tuple(outgoing.get(state, ())))
            for state in states
            if config.is_terminal(state) and outgoing.get(state)
        )

    sccs = tarjan_scc(states, edges)
    bottoms = bottom_sccs(sccs, edges)
    is_success = config.is_success or (lambda state: False)
    non_terminating: list[NonTerminatingComponent] = []
    for component in bottoms:
        has_terminal = any(config.is_terminal(state) for state in component)
        has_success = any(is_success(state) for state in component)
        if not has_terminal and not has_success:
            non_terminating.append(
                NonTerminatingComponent(
                    states=component,
                    reason="bottom SCC has no terminal or success state",
                    outgoing_edges=(),
                )
            )

    unreachable_success = False
    if config.required_success:
        unreachable_success = not any(is_success(state) for state in states)

    ok = (
        not stuck_states
        and not non_terminating
        and not unreachable_success
        and not terminal_outgoing
    )
    return LoopCheckReport(
        ok=ok,
        stuck_states=stuck_states,
        non_terminating_components=tuple(non_terminating),
        unreachable_success=unreachable_success,
        terminal_with_outgoing_edges=terminal_outgoing,
        graph_summary={"states": len(states), "edges": len(edges), "sccs": len(sccs)},
        reachable_states=states,
        edges=edges,
        sccs=sccs,
        bottom_sccs=bottoms,
    )


__all__ = [
    "GraphEdge",
    "LoopCheckConfig",
    "LoopCheckReport",
    "NonTerminatingComponent",
    "TerminalOutgoing",
    "bottom_sccs",
    "build_reachable_graph",
    "check_loops",
    "tarjan_scc",
]
