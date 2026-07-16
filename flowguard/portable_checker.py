"""Reference execution and compositional checks for portable FlowGuard models."""

from __future__ import annotations

import json
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Sequence

from .portable_model import (
    PortableModel,
    PortableTemporalObligation,
    PortableTransition,
    RefinementBinding,
    canonical_identity,
    canonical_json_bytes,
    validate_portable_model,
)


PORTABLE_CHECK_STATUSES = ("pass", "fail", "blocked", "invalid")


def _symbol_key(value: Any) -> bytes:
    return canonical_json_bytes(value)


@dataclass(frozen=True)
class PortableTraceStep:
    transition_id: str
    source_state: str
    input_symbol: Any
    output_symbol: Any
    target_state: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "transition_id": self.transition_id,
            "source_state": self.source_state,
            "input_symbol": self.input_symbol,
            "output_symbol": self.output_symbol,
            "target_state": self.target_state,
        }


@dataclass(frozen=True)
class PortableTrace:
    initial_state: str
    steps: tuple[PortableTraceStep, ...]
    terminal_state: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "initial_state": self.initial_state,
            "steps": [step.to_dict() for step in self.steps],
            "terminal_state": self.terminal_state,
        }


@dataclass(frozen=True)
class PortableFinding:
    finding_id: str
    message: str
    obligation_id: str = ""
    state_ids: tuple[str, ...] = ()
    transition_ids: tuple[str, ...] = ()
    details: Mapping[str, Any] = field(default_factory=dict, compare=False)

    def to_dict(self) -> dict[str, Any]:
        return {
            "finding_id": self.finding_id,
            "message": self.message,
            "obligation_id": self.obligation_id,
            "state_ids": list(self.state_ids),
            "transition_ids": list(self.transition_ids),
            "details": dict(self.details),
        }


@dataclass(frozen=True)
class PortableExecutionReport:
    status: str
    model_id: str
    model_fingerprint: str
    traces: tuple[PortableTrace, ...]
    findings: tuple[PortableFinding, ...] = ()
    blockers: tuple[str, ...] = ()
    claim_boundary: str = (
        "Execution covers only the declared finite input sequence and explicit portable relation."
    )

    @property
    def ok(self) -> bool:
        return self.status == "pass"

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifact_type": "flowguard_portable_execution_report",
            "status": self.status,
            "ok": self.ok,
            "model_id": self.model_id,
            "model_fingerprint": self.model_fingerprint,
            "traces": [trace.to_dict() for trace in self.traces],
            "findings": [finding.to_dict() for finding in self.findings],
            "blockers": list(self.blockers),
            "claim_boundary": self.claim_boundary,
        }


@dataclass(frozen=True)
class PortableCheckReport:
    status: str
    model_id: str
    model_fingerprint: str
    findings: tuple[PortableFinding, ...] = ()
    counterexamples: tuple[PortableTrace, ...] = ()
    checked_obligation_ids: tuple[str, ...] = ()
    blockers: tuple[str, ...] = ()
    skipped_checks: tuple[str, ...] = ()
    residual_risk: tuple[str, ...] = ()
    claim_boundary: str = (
        "The report covers only the explicit finite portable graph and declared obligations; "
        "domain truth and production implementation conformance require separate evidence."
    )

    @property
    def ok(self) -> bool:
        return self.status == "pass"

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifact_type": "flowguard_portable_check_report",
            "status": self.status,
            "ok": self.ok,
            "model_id": self.model_id,
            "model_fingerprint": self.model_fingerprint,
            "findings": [finding.to_dict() for finding in self.findings],
            "counterexamples": [trace.to_dict() for trace in self.counterexamples],
            "checked_obligation_ids": list(self.checked_obligation_ids),
            "blockers": list(self.blockers),
            "skipped_checks": list(self.skipped_checks),
            "residual_risk": list(self.residual_risk),
            "claim_boundary": self.claim_boundary,
        }

    def to_json_text(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent, sort_keys=True)

    def format_text(self, max_findings: int = 5) -> str:
        lines = [
            "=== flowguard portable check ===",
            f"status: {self.status}",
            f"model: {self.model_id}",
            f"identity: {self.model_fingerprint}",
            f"obligations: {len(self.checked_obligation_ids)}",
            f"findings: {len(self.findings)}",
        ]
        for finding in self.findings[:max_findings]:
            lines.append(f"- {finding.finding_id}: {finding.message}")
        if self.blockers:
            lines.append("blockers: " + "; ".join(self.blockers))
        lines.append(f"claim_boundary: {self.claim_boundary}")
        return "\n".join(lines)


def _step(transition: PortableTransition) -> PortableTraceStep:
    return PortableTraceStep(
        transition_id=transition.transition_id,
        source_state=transition.source_state,
        input_symbol=transition.input_symbol,
        output_symbol=transition.output_symbol,
        target_state=transition.target_state,
    )


def execute_portable_model(
    model: PortableModel,
    input_sequence: Sequence[Any],
    *,
    max_traces: int = 10000,
) -> PortableExecutionReport:
    errors = validate_portable_model(model)
    if errors:
        return PortableExecutionReport(
            status="invalid",
            model_id=model.model_id,
            model_fingerprint=model.fingerprint,
            traces=(),
            findings=tuple(
                PortableFinding("portable_model_invalid", message) for message in errors
            ),
        )
    if max_traces <= 0:
        return PortableExecutionReport(
            status="blocked",
            model_id=model.model_id,
            model_fingerprint=model.fingerprint,
            traces=(),
            blockers=("max_traces must be positive",),
        )
    by_source_input: dict[tuple[str, bytes], list[PortableTransition]] = {}
    for transition in model.transitions:
        by_source_input.setdefault(
            (transition.source_state, _symbol_key(transition.input_symbol)), []
        ).append(transition)
    active: list[tuple[str, tuple[PortableTraceStep, ...], str]] = [
        (state_id, (), state_id) for state_id in model.initial_state_ids
    ]
    for input_symbol in input_sequence:
        next_active: list[tuple[str, tuple[PortableTraceStep, ...], str]] = []
        for state_id, steps, initial_state in active:
            for transition in by_source_input.get((state_id, _symbol_key(input_symbol)), ()):
                next_active.append(
                    (transition.target_state, steps + (_step(transition),), initial_state)
                )
                if len(next_active) > max_traces:
                    return PortableExecutionReport(
                        status="blocked",
                        model_id=model.model_id,
                        model_fingerprint=model.fingerprint,
                        traces=tuple(
                            PortableTrace(initial, trace_steps, terminal)
                            for terminal, trace_steps, initial in next_active[:max_traces]
                        ),
                        blockers=("trace exploration exceeded max_traces",),
                    )
        active = next_active
        if not active:
            break
    traces = tuple(
        PortableTrace(initial, steps, state_id) for state_id, steps, initial in active
    )
    return PortableExecutionReport(
        status="pass",
        model_id=model.model_id,
        model_fingerprint=model.fingerprint,
        traces=traces,
    )


def _reachable(
    model: PortableModel,
    *,
    max_states: int,
) -> tuple[tuple[str, ...], tuple[PortableTransition, ...], bool]:
    outgoing: dict[str, list[PortableTransition]] = {}
    for transition in model.transitions:
        outgoing.setdefault(transition.source_state, []).append(transition)
    queue = deque(model.initial_state_ids)
    seen: set[str] = set(model.initial_state_ids)
    edges: list[PortableTransition] = []
    truncated = False
    while queue:
        state_id = queue.popleft()
        for transition in outgoing.get(state_id, ()):
            edges.append(transition)
            if transition.target_state not in seen:
                seen.add(transition.target_state)
                if len(seen) > max_states:
                    truncated = True
                    return tuple(sorted(seen)), tuple(edges), truncated
                queue.append(transition.target_state)
    return tuple(sorted(seen)), tuple(edges), truncated


def _tarjan(
    states: Iterable[str], transitions: Iterable[PortableTransition]
) -> tuple[tuple[str, ...], ...]:
    adjacency: dict[str, list[str]] = {state: [] for state in states}
    for transition in transitions:
        adjacency.setdefault(transition.source_state, []).append(transition.target_state)
    index = 0
    stack: list[str] = []
    on_stack: set[str] = set()
    indices: dict[str, int] = {}
    lowlinks: dict[str, int] = {}
    result: list[tuple[str, ...]] = []

    def visit(state: str) -> None:
        nonlocal index
        indices[state] = index
        lowlinks[state] = index
        index += 1
        stack.append(state)
        on_stack.add(state)
        for target in adjacency.get(state, ()):
            if target not in indices:
                visit(target)
                lowlinks[state] = min(lowlinks[state], lowlinks[target])
            elif target in on_stack:
                lowlinks[state] = min(lowlinks[state], indices[target])
        if lowlinks[state] == indices[state]:
            component: list[str] = []
            while True:
                member = stack.pop()
                on_stack.remove(member)
                component.append(member)
                if member == state:
                    break
            result.append(tuple(sorted(component)))

    for state in sorted(adjacency):
        if state not in indices:
            visit(state)
    return tuple(result)


def _is_cyclic(component: Sequence[str], edges: Sequence[PortableTransition]) -> bool:
    members = set(component)
    return len(members) > 1 or any(
        edge.source_state in members and edge.target_state in members for edge in edges
    )


def _shortest_trace(
    model: PortableModel,
    target_states: set[str],
    *,
    allowed_states: set[str] | None = None,
) -> PortableTrace | None:
    outgoing: dict[str, list[PortableTransition]] = {}
    for transition in model.transitions:
        outgoing.setdefault(transition.source_state, []).append(transition)
    queue: deque[tuple[str, str, tuple[PortableTraceStep, ...]]] = deque(
        (state_id, state_id, ()) for state_id in model.initial_state_ids
    )
    seen = set(model.initial_state_ids)
    while queue:
        state_id, initial, steps = queue.popleft()
        if state_id in target_states:
            return PortableTrace(initial, steps, state_id)
        for transition in outgoing.get(state_id, ()):
            if allowed_states is not None and transition.target_state not in allowed_states:
                continue
            if transition.target_state in seen:
                continue
            seen.add(transition.target_state)
            queue.append(
                (transition.target_state, initial, steps + (_step(transition),))
            )
    return None


def _subgraph_from_trigger(
    trigger: str,
    targets: set[str],
    edges: Sequence[PortableTransition],
) -> tuple[set[str], tuple[PortableTransition, ...]]:
    if trigger in targets:
        return set(), ()
    outgoing: dict[str, list[PortableTransition]] = {}
    for edge in edges:
        outgoing.setdefault(edge.source_state, []).append(edge)
    queue = deque([trigger])
    states = {trigger}
    selected: list[PortableTransition] = []
    while queue:
        state_id = queue.popleft()
        for edge in outgoing.get(state_id, ()):
            if edge.target_state in targets:
                continue
            selected.append(edge)
            if edge.target_state not in states:
                states.add(edge.target_state)
                queue.append(edge.target_state)
    return states, tuple(selected)


def _fairness_forces_escape(
    component: Sequence[str],
    all_edges: Sequence[PortableTransition],
    fairness: Sequence[PortableTemporalObligation],
) -> str:
    members = set(component)
    for obligation in fairness:
        enabled_states = set(obligation.trigger_state_ids)
        fair_ids = set(obligation.transition_ids)
        if not members or not members.issubset(enabled_states):
            continue
        fair_from_component = [
            edge
            for edge in all_edges
            if edge.source_state in members and edge.transition_id in fair_ids
        ]
        if not fair_from_component:
            continue
        if not all(
            any(edge.source_state == state for edge in fair_from_component)
            for state in members
        ):
            continue
        if all(edge.target_state not in members for edge in fair_from_component):
            return obligation.obligation_id
    return ""


def _eventual_failure(
    model: PortableModel,
    trigger: str,
    targets: set[str],
    reachable_edges: Sequence[PortableTransition],
    fairness: Sequence[PortableTemporalObligation],
) -> tuple[str, tuple[str, ...], tuple[str, ...], Mapping[str, Any]] | None:
    states, edges = _subgraph_from_trigger(trigger, targets, reachable_edges)
    if not states:
        return None
    outgoing_all: dict[str, list[PortableTransition]] = {}
    for edge in reachable_edges:
        outgoing_all.setdefault(edge.source_state, []).append(edge)
    deadends = tuple(
        sorted(
            state
            for state in states
            if not outgoing_all.get(state)
        )
    )
    if deadends:
        return "eventual_dead_end", deadends[:1], (), {}
    for component in _tarjan(states, edges):
        if not _is_cyclic(component, edges):
            continue
        fairness_id = _fairness_forces_escape(component, reachable_edges, fairness)
        if fairness_id:
            continue
        internal = tuple(
            edge.transition_id
            for edge in edges
            if edge.source_state in component and edge.target_state in component
        )
        return "eventual_cycle", tuple(component), internal, {}
    return None


def _bounded_failure(
    trigger: str,
    targets: set[str],
    max_steps: int,
    reachable_edges: Sequence[PortableTransition],
) -> tuple[tuple[str, ...], tuple[str, ...]] | None:
    outgoing: dict[str, list[PortableTransition]] = {}
    for edge in reachable_edges:
        outgoing.setdefault(edge.source_state, []).append(edge)
    queue: deque[tuple[str, tuple[str, ...], tuple[str, ...]]] = deque(
        [(trigger, (trigger,), ())]
    )
    while queue:
        state_id, states, transitions = queue.popleft()
        if state_id in targets:
            continue
        depth = len(transitions)
        if depth >= max_steps:
            return states, transitions
        next_edges = outgoing.get(state_id, ())
        if not next_edges:
            return states, transitions
        for edge in next_edges:
            queue.append(
                (
                    edge.target_state,
                    states + (edge.target_state,),
                    transitions + (edge.transition_id,),
                )
            )
    return None


def check_portable_model(
    model: PortableModel,
    *,
    max_states: int = 10000,
) -> PortableCheckReport:
    errors = validate_portable_model(model)
    if errors:
        return PortableCheckReport(
            status="invalid",
            model_id=model.model_id,
            model_fingerprint=model.fingerprint,
            findings=tuple(
                PortableFinding("portable_model_invalid", error) for error in errors
            ),
        )
    if max_states <= 0:
        return PortableCheckReport(
            status="blocked",
            model_id=model.model_id,
            model_fingerprint=model.fingerprint,
            blockers=("max_states must be positive",),
        )
    reachable_states, reachable_edges, truncated = _reachable(model, max_states=max_states)
    if truncated:
        return PortableCheckReport(
            status="blocked",
            model_id=model.model_id,
            model_fingerprint=model.fingerprint,
            blockers=("reachable graph exceeded max_states",),
        )
    reachable = set(reachable_states)
    findings: list[PortableFinding] = []
    counterexamples: list[PortableTrace] = []
    checked: list[str] = []

    for invariant in model.invariants:
        checked.append(invariant.invariant_id)
        forbidden = reachable.intersection(invariant.forbidden_state_ids)
        for state_id in sorted(forbidden):
            findings.append(
                PortableFinding(
                    "invariant_forbidden_state_reachable",
                    invariant.description or f"forbidden state {state_id!r} is reachable",
                    obligation_id=invariant.invariant_id,
                    state_ids=(state_id,),
                )
            )
            trace = _shortest_trace(model, {state_id})
            if trace:
                counterexamples.append(trace)

    fairness = tuple(
        item for item in model.temporal_obligations if item.kind == "weak_fairness"
    )
    reachable_transition_ids = {edge.transition_id for edge in reachable_edges}
    for obligation in fairness:
        checked.append(obligation.obligation_id)
        missing = tuple(
            sorted(set(obligation.transition_ids) - reachable_transition_ids)
        )
        if missing:
            findings.append(
                PortableFinding(
                    "fairness_transition_unreachable",
                    "weak-fairness transitions are never enabled in the reachable graph",
                    obligation_id=obligation.obligation_id,
                    transition_ids=missing,
                )
            )

    for obligation in model.temporal_obligations:
        if obligation.kind == "weak_fairness":
            continue
        checked.append(obligation.obligation_id)
        triggers = tuple(
            state_id
            for state_id in (obligation.trigger_state_ids or model.initial_state_ids)
            if state_id in reachable
        )
        targets = (
            set(model.terminal_state_ids)
            if obligation.kind == "terminal_progress"
            else set(obligation.target_state_ids)
        )
        if not triggers:
            findings.append(
                PortableFinding(
                    "temporal_trigger_unreachable",
                    "temporal obligation has no reachable trigger state",
                    obligation_id=obligation.obligation_id,
                )
            )
            continue
        if not targets:
            findings.append(
                PortableFinding(
                    "temporal_target_missing",
                    "temporal obligation has no target states",
                    obligation_id=obligation.obligation_id,
                )
            )
            continue
        for trigger in triggers:
            failure = _eventual_failure(
                model, trigger, targets, reachable_edges, fairness
            )
            if failure:
                finding_id, states, transitions, details = failure
                findings.append(
                    PortableFinding(
                        finding_id,
                        "a target-avoiding dead end or fair cycle violates universal eventuality",
                        obligation_id=obligation.obligation_id,
                        state_ids=states,
                        transition_ids=transitions,
                        details=details,
                    )
                )
                trace = _shortest_trace(model, set(states))
                if trace:
                    counterexamples.append(trace)
                break
            if obligation.kind == "bounded_eventually":
                bounded = _bounded_failure(
                    trigger,
                    targets,
                    int(obligation.max_steps or 0),
                    reachable_edges,
                )
                if bounded:
                    states, transitions = bounded
                    findings.append(
                        PortableFinding(
                            "bounded_eventually_exceeded",
                            f"one target-avoiding path exceeds {obligation.max_steps} steps",
                            obligation_id=obligation.obligation_id,
                            state_ids=states,
                            transition_ids=transitions,
                            details={"max_steps": obligation.max_steps},
                        )
                    )
                    break

    return PortableCheckReport(
        status="pass" if not findings else "fail",
        model_id=model.model_id,
        model_fingerprint=model.fingerprint,
        findings=tuple(findings),
        counterexamples=tuple(counterexamples),
        checked_obligation_ids=tuple(checked),
        residual_risk=(
            "Portable token names and state payloads are declarations; their domain truth is not inferred.",
        ),
    )


def _reachable_state_ids(model: PortableModel) -> set[str]:
    states, _edges, _truncated = _reachable(model, max_states=max(1, len(model.states) + 1))
    return set(states)


def check_refinement(
    parent: PortableModel,
    child: PortableModel,
    binding: RefinementBinding,
) -> PortableCheckReport:
    findings: list[PortableFinding] = []
    for role, model in (("parent", parent), ("child", child)):
        for error in validate_portable_model(model):
            findings.append(
                PortableFinding("portable_model_invalid", f"{role}: {error}")
            )
    if findings:
        return PortableCheckReport(
            status="invalid",
            model_id=f"{parent.model_id}<={child.model_id}",
            model_fingerprint=canonical_identity(
                {"parent": parent.fingerprint, "child": child.fingerprint}
            ),
            findings=tuple(findings),
        )
    if binding.parent_model_id != parent.model_id or binding.child_model_id != child.model_id:
        findings.append(
            PortableFinding(
                "refinement_model_identity_mismatch",
                "binding model ids do not match the supplied parent and child",
            )
        )
    if binding.parent_model_fingerprint and binding.parent_model_fingerprint != parent.fingerprint:
        findings.append(
            PortableFinding("refinement_parent_stale", "parent model fingerprint is stale")
        )
    if binding.child_model_fingerprint and binding.child_model_fingerprint != child.fingerprint:
        findings.append(
            PortableFinding("refinement_child_stale", "child model fingerprint is stale")
        )

    state_map = dict(binding.state_mapping)
    transition_map = dict(binding.transition_mapping)
    stutters = set(binding.allowed_stutter_transition_ids)
    parent_states = {item.state_id for item in parent.states}
    parent_transitions = {item.transition_id: item for item in parent.transitions}
    child_transitions = {item.transition_id: item for item in child.transitions}
    reachable_child_states = _reachable_state_ids(child)
    reachable_child_transitions = tuple(
        transition
        for transition in child.transitions
        if transition.source_state in reachable_child_states
    )

    for child_state in sorted(reachable_child_states):
        mapped = state_map.get(child_state, "")
        if not mapped:
            findings.append(
                PortableFinding(
                    "refinement_state_unmapped",
                    "reachable child state lacks a parent mapping",
                    state_ids=(child_state,),
                )
            )
        elif mapped not in parent_states:
            findings.append(
                PortableFinding(
                    "refinement_state_target_missing",
                    "child state maps to an unknown parent state",
                    state_ids=(child_state, mapped),
                )
            )

    for initial in child.initial_state_ids:
        if state_map.get(initial) not in set(parent.initial_state_ids):
            findings.append(
                PortableFinding(
                    "refinement_initial_state_mismatch",
                    "child initial state does not map to a parent initial state",
                    state_ids=(initial, state_map.get(initial, "")),
                )
            )
    for terminal in child.terminal_state_ids:
        if state_map.get(terminal) not in set(parent.terminal_state_ids):
            findings.append(
                PortableFinding(
                    "refinement_terminal_state_mismatch",
                    "child terminal state does not map to a parent terminal state",
                    state_ids=(terminal, state_map.get(terminal, "")),
                )
            )

    extra_transition_mappings = sorted(set(transition_map) - set(child_transitions))
    if extra_transition_mappings:
        findings.append(
            PortableFinding(
                "refinement_unknown_child_transition_mapping",
                "binding maps transitions absent from the child model",
                transition_ids=tuple(extra_transition_mappings),
            )
        )
    for child_transition in reachable_child_transitions:
        source = state_map.get(child_transition.source_state, "")
        target = state_map.get(child_transition.target_state, "")
        if child_transition.transition_id in stutters:
            if source and target and source != target:
                findings.append(
                    PortableFinding(
                        "refinement_invalid_stutter",
                        "declared child stutter changes the mapped parent state",
                        state_ids=(source, target),
                        transition_ids=(child_transition.transition_id,),
                    )
                )
            continue
        parent_transition_id = transition_map.get(child_transition.transition_id, "")
        if not parent_transition_id:
            findings.append(
                PortableFinding(
                    "refinement_transition_unmapped",
                    "reachable child transition lacks a parent mapping",
                    transition_ids=(child_transition.transition_id,),
                )
            )
            continue
        parent_transition = parent_transitions.get(parent_transition_id)
        if parent_transition is None:
            findings.append(
                PortableFinding(
                    "refinement_parent_transition_missing",
                    "child transition maps to an unknown parent transition",
                    transition_ids=(child_transition.transition_id, parent_transition_id),
                )
            )
            continue
        mismatches: list[str] = []
        if source != parent_transition.source_state:
            mismatches.append("source_state")
        if target != parent_transition.target_state:
            mismatches.append("target_state")
        if _symbol_key(child_transition.input_symbol) != _symbol_key(parent_transition.input_symbol):
            mismatches.append("input_symbol")
        if _symbol_key(child_transition.output_symbol) != _symbol_key(parent_transition.output_symbol):
            mismatches.append("output_symbol")
        if mismatches:
            findings.append(
                PortableFinding(
                    "refinement_step_mismatch",
                    "child transition does not simulate its mapped parent transition",
                    state_ids=(source, target),
                    transition_ids=(child_transition.transition_id, parent_transition_id),
                    details={"mismatched_fields": mismatches},
                )
            )

    stronger_assumptions = tuple(sorted(set(child.assumptions) - set(parent.assumptions)))
    missing_guarantees = tuple(sorted(set(parent.guarantees) - set(child.guarantees)))
    if stronger_assumptions:
        findings.append(
            PortableFinding(
                "refinement_stronger_child_assumption",
                "child requires assumptions not required by the parent",
                details={"tokens": list(stronger_assumptions)},
            )
        )
    if missing_guarantees:
        findings.append(
            PortableFinding(
                "refinement_missing_parent_guarantee",
                "child does not provide every parent guarantee",
                details={"tokens": list(missing_guarantees)},
            )
        )

    return PortableCheckReport(
        status="pass" if not findings else "fail",
        model_id=f"{parent.model_id}<={child.model_id}",
        model_fingerprint=canonical_identity(
            {
                "parent": parent.fingerprint,
                "child": child.fingerprint,
                "binding": binding.to_dict(),
            }
        ),
        findings=tuple(findings),
        checked_obligation_ids=(
            "refinement.mapping.complete",
            "refinement.step.simulation",
            "refinement.contract.substitutability",
        ),
        residual_risk=("Refinement validates the declared abstraction mapping, not domain truth.",),
        claim_boundary=(
            "Refinement covers reachable finite child states, declared mappings, and contract tokens only."
        ),
    )


def check_composition(
    models: Sequence[PortableModel],
    *,
    environment_guarantees: Sequence[str] = (),
) -> PortableCheckReport:
    findings: list[PortableFinding] = []
    if not models:
        return PortableCheckReport(
            status="invalid",
            model_id="composition",
            model_fingerprint=canonical_identity([]),
            findings=(PortableFinding("composition_empty", "composition requires at least one model"),),
        )
    model_ids = [model.model_id for model in models]
    if len(set(model_ids)) != len(model_ids):
        findings.append(
            PortableFinding("composition_duplicate_model_id", "component model ids must be unique")
        )
    for model in models:
        report = check_portable_model(model)
        if not report.ok:
            findings.append(
                PortableFinding(
                    "composition_component_not_pass",
                    f"component {model.model_id!r} did not pass its own portable checks",
                    details={"component_status": report.status},
                )
            )
    environment = set(environment_guarantees)
    for model in models:
        providers = set(environment)
        for peer in models:
            if peer.model_id != model.model_id:
                providers.update(peer.guarantees)
        missing = tuple(sorted(set(model.assumptions) - providers))
        if missing:
            findings.append(
                PortableFinding(
                    "composition_assumption_unprovided",
                    f"component {model.model_id!r} has assumptions without an environment or peer provider",
                    details={"component_id": model.model_id, "tokens": list(missing)},
                )
            )
    available_tokens = set(environment)
    for model in models:
        available_tokens.update(model.guarantees)
    seen_conflicts: set[tuple[str, str]] = set()
    for model in models:
        for pair in model.conflicts:
            normalized = tuple(sorted(pair))
            if normalized in seen_conflicts:
                continue
            seen_conflicts.add(normalized)
            if set(normalized).issubset(available_tokens):
                findings.append(
                    PortableFinding(
                        "composition_guarantee_conflict",
                        "declared conflicting guarantees are simultaneously present",
                        details={"tokens": list(normalized)},
                    )
                )
    return PortableCheckReport(
        status="pass" if not findings else "fail",
        model_id="composition:" + "+".join(sorted(model_ids)),
        model_fingerprint=canonical_identity(
            {
                "models": {model.model_id: model.fingerprint for model in models},
                "environment_guarantees": sorted(environment),
            }
        ),
        findings=tuple(findings),
        checked_obligation_ids=(
            "composition.components.pass",
            "composition.assumptions.provided",
            "composition.conflicts.absent",
        ),
        residual_risk=("Contract tokens are declared interfaces and do not prove external facts.",),
        claim_boundary=(
            "Composition proves declared finite component checks and token provider closure only."
        ),
    )


__all__ = [
    "PORTABLE_CHECK_STATUSES",
    "PortableCheckReport",
    "PortableExecutionReport",
    "PortableFinding",
    "PortableTrace",
    "PortableTraceStep",
    "check_composition",
    "check_portable_model",
    "check_refinement",
    "execute_portable_model",
]
