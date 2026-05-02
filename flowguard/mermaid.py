"""Mermaid source exporters for FlowGuard traces and state graphs."""

from __future__ import annotations

from typing import Any, Iterable, Sequence


_VALID_DIRECTIONS = {"TB", "TD", "BT", "RL", "LR"}


def _validate_direction(direction: str) -> str:
    normalized = str(direction or "TD").upper()
    if normalized not in _VALID_DIRECTIONS:
        raise ValueError(
            "Mermaid flowchart direction must be one of "
            + ", ".join(sorted(_VALID_DIRECTIONS))
        )
    return normalized


def _short_repr(value: Any, max_label_chars: int | None) -> str:
    text = repr(value)
    if max_label_chars is not None and max_label_chars >= 0 and len(text) > max_label_chars:
        if max_label_chars <= 3:
            return text[:max_label_chars]
        return text[: max_label_chars - 3] + "..."
    return text


def _escape_text(text: str) -> str:
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("|", "&#124;")
    )


def _node_label(lines: Iterable[str]) -> str:
    return "<br/>".join(_escape_text(line) for line in lines if line != "")


def _edge_label(text: str) -> str:
    return _escape_text(text).replace("\n", "<br/>")


def _comment_text(text: str) -> str:
    return " ".join(str(text).split())


def _append_unique(values: list[Any], value: Any) -> None:
    if not any(existing == value for existing in values):
        values.append(value)


def _edge_text(edge: Any, include_reasons: bool) -> str:
    label = str(getattr(edge, "label", "") or "")
    reason = str(getattr(edge, "reason", "") or "")
    if include_reasons and reason:
        if label:
            return f"{label}: {reason}"
        return reason
    return label


def mermaid_code_block(source: str) -> str:
    """Wrap Mermaid source in a Markdown code fence."""

    return "```mermaid\n" + source.rstrip() + "\n```"


def trace_to_mermaid_text(
    trace: Any,
    *,
    direction: str = "TD",
    title: str = "FlowGuard trace",
    include_states: bool = True,
    max_label_chars: int | None = 160,
) -> str:
    """Return Mermaid flowchart source for one FlowGuard trace.

    This is an explicit export helper. It does not change Trace.format_text()
    or any default report output.
    """

    graph_direction = _validate_direction(direction)
    lines = [f"flowchart {graph_direction}"]
    if title:
        lines.append(f"  %% {_comment_text(title)}")

    start_label = ["start"]
    if include_states:
        start_label.append("state: " + _short_repr(getattr(trace, "initial_state", None), max_label_chars))
    lines.append(f'  n0["{_node_label(start_label)}"]')

    previous = "n0"
    for index, step in enumerate(getattr(trace, "steps", ()), start=1):
        node_id = f"n{index}"
        step_label = [f"{index}. {getattr(step, 'function_name', '')}"]
        step_label.append("input: " + _short_repr(getattr(step, "function_input", None), max_label_chars))
        step_label.append("output: " + _short_repr(getattr(step, "function_output", None), max_label_chars))
        label = str(getattr(step, "label", "") or "")
        if label:
            step_label.append("label: " + label)
        if include_states:
            step_label.append("state: " + _short_repr(getattr(step, "new_state", None), max_label_chars))
        lines.append(f'  {node_id}["{_node_label(step_label)}"]')
        edge_label = label or str(getattr(step, "function_name", "") or f"step {index}")
        lines.append(f"  {previous} -->|{_edge_label(edge_label)}| {node_id}")
        previous = node_id

    return "\n".join(lines)


def graph_to_mermaid_text(
    edges: Sequence[Any],
    *,
    states: Sequence[Any] = (),
    initial_states: Sequence[Any] = (),
    direction: str = "TD",
    title: str = "FlowGuard state graph",
    include_reasons: bool = False,
    max_label_chars: int | None = 160,
) -> str:
    """Return Mermaid flowchart source for a state graph.

    Edges may be FlowGuard GraphEdge objects or edge-like objects with
    old_state, new_state, label, and optional reason attributes.
    """

    graph_direction = _validate_direction(direction)
    ordered_states: list[Any] = []
    for state in states:
        _append_unique(ordered_states, state)
    for state in initial_states:
        _append_unique(ordered_states, state)
    for edge in edges:
        _append_unique(ordered_states, getattr(edge, "old_state"))
        _append_unique(ordered_states, getattr(edge, "new_state"))

    lines = [f"flowchart {graph_direction}"]
    if title:
        lines.append(f"  %% {_comment_text(title)}")

    if not ordered_states:
        lines.append('  n0["empty graph"]')
        return "\n".join(lines)

    node_ids = {index: f"n{index}" for index in range(len(ordered_states))}
    for index, state in enumerate(ordered_states):
        label = _short_repr(state, max_label_chars)
        lines.append(f'  {node_ids[index]}["{_node_label((label,))}"]')

    for edge in edges:
        old_index = next(index for index, state in enumerate(ordered_states) if state == getattr(edge, "old_state"))
        new_index = next(index for index, state in enumerate(ordered_states) if state == getattr(edge, "new_state"))
        label = _edge_text(edge, include_reasons)
        if label:
            lines.append(
                f"  {node_ids[old_index]} -->|{_edge_label(label)}| {node_ids[new_index]}"
            )
        else:
            lines.append(f"  {node_ids[old_index]} --> {node_ids[new_index]}")

    if initial_states:
        initial_ids = [
            node_ids[index]
            for index, state in enumerate(ordered_states)
            if any(state == initial for initial in initial_states)
        ]
        if initial_ids:
            lines.append("  classDef flowguardInitial fill:#eef6ff,stroke:#2563eb,color:#111827")
            lines.append(f"  class {','.join(initial_ids)} flowguardInitial")

    return "\n".join(lines)


def loop_report_to_mermaid_text(
    report: Any,
    *,
    direction: str = "TD",
    title: str = "FlowGuard loop graph",
    include_reasons: bool = False,
    max_label_chars: int | None = 160,
) -> str:
    """Return Mermaid flowchart source for a LoopCheckReport."""

    return graph_to_mermaid_text(
        tuple(getattr(report, "edges", ())),
        states=tuple(getattr(report, "reachable_states", ())),
        direction=direction,
        title=title,
        include_reasons=include_reasons,
        max_label_chars=max_label_chars,
    )


__all__ = [
    "graph_to_mermaid_text",
    "loop_report_to_mermaid_text",
    "mermaid_code_block",
    "trace_to_mermaid_text",
]
