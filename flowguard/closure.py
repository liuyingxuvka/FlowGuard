"""Executable closure checks for handoffs between child models."""
from __future__ import annotations
import json
from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence
from ._normalization import string_sequence as _as_tuple
from .export import to_jsonable
from .core import Invariant, InvariantResult
MESH_CLOSURE_NORMAL_EXIT = 'normal_exit'
MESH_CLOSURE_FAILURE_EXIT = 'failure_exit'
MESH_CLOSURE_OUT_OF_SCOPE = 'out_of_scope'
MESH_CLOSURE_TERMINAL_SIDE_EFFECT = 'terminal_side_effect'
ALLOWED_MESH_CLOSURE_TERMINALS = {MESH_CLOSURE_NORMAL_EXIT, MESH_CLOSURE_FAILURE_EXIT, MESH_CLOSURE_OUT_OF_SCOPE,
    MESH_CLOSURE_TERMINAL_SIDE_EFFECT}

@dataclass(frozen=True)
class MeshClosureTransition:
    """One model-to-model closure transition over abstract handoff tokens."""
    transition_id: str
    consumes: tuple[str, ...] = ()
    emits: tuple[str, ...] = ()
    consumer_model_id: str = ''
    loop: bool = False
    progress_rule: str = ''
    max_iterations: int | None = None
    repeat_input_tokens: tuple[str, ...] = ()
    progress_tokens: tuple[str, ...] = ()
    repair_feedback_tokens: tuple[str, ...] = ()
    blocker_tokens: tuple[str, ...] = ()
    rationale: str = ''

    def __post_init__(self) -> None:
        object.__setattr__(self, 'transition_id', str(self.transition_id))
        object.__setattr__(self, 'consumes', _as_tuple(self.consumes))
        object.__setattr__(self, 'emits', _as_tuple(self.emits))
        object.__setattr__(self, 'consumer_model_id', str(self.consumer_model_id))
        object.__setattr__(self, 'loop', bool(self.loop))
        if self.max_iterations is not None:
            object.__setattr__(self, 'max_iterations', int(self.max_iterations))
        object.__setattr__(self, 'progress_rule', str(self.progress_rule))
        object.__setattr__(self, 'repeat_input_tokens', _as_tuple(self.repeat_input_tokens))
        object.__setattr__(self, 'progress_tokens', _as_tuple(self.progress_tokens))
        object.__setattr__(self, 'repair_feedback_tokens', _as_tuple(self.repair_feedback_tokens))
        object.__setattr__(self, 'blocker_tokens', _as_tuple(self.blocker_tokens))
        object.__setattr__(self, 'rationale', str(self.rationale))

    def has_progress_rule(self) -> bool:
        return bool(self.progress_rule) or self.max_iterations is not None or bool(self.progress_tokens) or bool(self.blocker_tokens)

    def has_structured_repeat_disposition(self) -> bool:
        return bool(self.progress_tokens or self.blocker_tokens) or self.max_iterations is not None

    def to_dict(self) -> dict[str, Any]:
        return {'transition_id': self.transition_id, 'consumes': list(self.consumes), 'emits': list(self.emits),
            'consumer_model_id': self.consumer_model_id, 'loop': self.loop, 'progress_rule': self.progress_rule,
            'max_iterations': self.max_iterations, 'repeat_input_tokens': list(self.repeat_input_tokens),
            'progress_tokens': list(self.progress_tokens), 'repair_feedback_tokens': list(self.repair_feedback_tokens),
            'blocker_tokens': list(self.blocker_tokens), 'rationale': self.rationale}

@dataclass(frozen=True)
class MeshClosureJoin:
    """A parent-level join point that must consume all required handoff tokens."""
    join_id: str
    required_inputs: tuple[str, ...] = ()
    emits: tuple[str, ...] = ()
    rationale: str = ''

    def __post_init__(self) -> None:
        object.__setattr__(self, 'join_id', str(self.join_id))
        object.__setattr__(self, 'required_inputs', _as_tuple(self.required_inputs))
        object.__setattr__(self, 'emits', _as_tuple(self.emits))
        object.__setattr__(self, 'rationale', str(self.rationale))

    def to_dict(self) -> dict[str, Any]:
        return {'join_id': self.join_id, 'required_inputs': list(self.required_inputs), 'emits': list(self.emits),
            'rationale': self.rationale}

@dataclass(frozen=True)
class MeshClosureTerminal:
    """A terminal or explicit disposition for closure tokens."""
    terminal_id: str
    consumes: tuple[str, ...] = ()
    terminal_kind: str = MESH_CLOSURE_NORMAL_EXIT
    rationale: str = ''

    def __post_init__(self) -> None:
        object.__setattr__(self, 'terminal_id', str(self.terminal_id))
        object.__setattr__(self, 'consumes', _as_tuple(self.consumes))
        object.__setattr__(self, 'terminal_kind', str(self.terminal_kind))
        object.__setattr__(self, 'rationale', str(self.rationale))

    def to_dict(self) -> dict[str, Any]:
        return {'terminal_id': self.terminal_id, 'consumes': list(self.consumes), 'terminal_kind': self.terminal_kind,
            'rationale': self.rationale}

@dataclass(frozen=True)
class MeshClosureModel:
    """FlowGuard-style meta-model for parent/child model handoff closure."""
    parent_model_id: str
    root_entries: tuple[str, ...] = ()
    transitions: tuple[MeshClosureTransition, ...] = ()
    joins: tuple[MeshClosureJoin, ...] = ()
    terminals: tuple[MeshClosureTerminal, ...] = ()
    required_outputs: tuple[str, ...] = ()
    require_normal_exit: bool = True
    rationale: str = ''

    def __post_init__(self) -> None:
        object.__setattr__(self, 'parent_model_id', str(self.parent_model_id))
        object.__setattr__(self, 'root_entries', _as_tuple(self.root_entries))
        object.__setattr__(self, 'transitions', tuple(self.transitions))
        object.__setattr__(self, 'joins', tuple(self.joins))
        object.__setattr__(self, 'terminals', tuple(self.terminals))
        object.__setattr__(self, 'required_outputs', _as_tuple(self.required_outputs))
        object.__setattr__(self, 'require_normal_exit', bool(self.require_normal_exit))
        object.__setattr__(self, 'rationale', str(self.rationale))

    def to_dict(self) -> dict[str, Any]:
        return {'parent_model_id': self.parent_model_id, 'root_entries': list(self.root_entries),
            'transitions': [transition.to_dict() for transition in self.transitions], 'joins': [join.to_dict() for join in self.joins],
            'terminals': [terminal.to_dict() for terminal in self.terminals], 'required_outputs': list(self.required_outputs),
            'require_normal_exit': self.require_normal_exit, 'rationale': self.rationale}

@dataclass(frozen=True)
class MeshClosureFinding:
    """One closure-model finding from the executable handoff meta-model."""
    code: str
    message: str
    severity: str = 'blocker'
    model_id: str = ''
    item_id: str = ''
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, 'code', str(self.code))
        object.__setattr__(self, 'message', str(self.message))
        object.__setattr__(self, 'severity', str(self.severity))
        object.__setattr__(self, 'model_id', str(self.model_id))
        object.__setattr__(self, 'item_id', str(self.item_id))
        object.__setattr__(self, 'metadata', dict(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {'code': self.code, 'message': self.message, 'severity': self.severity, 'model_id': self.model_id, 'item_id': self.item_id,
            'metadata': to_jsonable(dict(self.metadata))}

@dataclass(frozen=True)
class MeshClosureReport:
    """Structured outcome of a mesh closure meta-model review."""
    ok: bool
    parent_model_id: str
    decision: str
    findings: tuple[MeshClosureFinding, ...] = ()
    reachable_tokens: tuple[str, ...] = ()
    summary: str = ''

    def __post_init__(self) -> None:
        object.__setattr__(self, 'parent_model_id', str(self.parent_model_id))
        object.__setattr__(self, 'decision', str(self.decision))
        object.__setattr__(self, 'findings', tuple(self.findings))
        object.__setattr__(self, 'reachable_tokens', _as_tuple(self.reachable_tokens))
        if not self.summary:
            status = 'OK' if self.ok else 'BLOCKED'
            object.__setattr__(self, 'summary',
                f'{status}: parent={self.parent_model_id} closure_decision={self.decision} findings={len(self.findings)}')

    def format_text(self, max_findings: int=10) -> str:
        lines = ['=== flowguard mesh closure review ===', f"status: {('OK' if self.ok else 'BLOCKED')}", f'parent: {self.parent_model_id}',
            f'decision: {self.decision}', f'findings: {len(self.findings)}']
        for finding in self.findings[:max_findings]:
            lines.extend(['', f'finding: {finding.code}', f'severity: {finding.severity}', f"model: {finding.model_id or '(none)'}",
                f"item: {finding.item_id or '(none)'}", f'message: {finding.message}'])
        return '\n'.join(lines)

    def to_dict(self) -> dict[str, Any]:
        return {'ok': self.ok, 'parent_model_id': self.parent_model_id, 'decision': self.decision,
            'findings': [finding.to_dict() for finding in self.findings], 'reachable_tokens': list(self.reachable_tokens),
            'summary': self.summary}

    def to_json_text(self, indent: int=2) -> str:
        return json.dumps(to_jsonable(self.to_dict()), indent=indent, sort_keys=True)

@dataclass(frozen=True)
class _ClosureState:
    available: frozenset[str]
    consumed: frozenset[str] = frozenset()
    completed_joins: frozenset[str] = frozenset()
    terminal_kind: str = ''

def _closure_consumed_tokens(model: MeshClosureModel) -> set[str]:
    tokens: set[str] = set()
    for transition in model.transitions:
        tokens.update(transition.consumes)
    for join in model.joins:
        tokens.update(join.required_inputs)
    for terminal in model.terminals:
        tokens.update(terminal.consumes)
    return tokens

def _closure_known_tokens(model: MeshClosureModel) -> set[str]:
    tokens = set(model.root_entries)
    tokens.update(model.required_outputs)
    for transition in model.transitions:
        tokens.update(transition.emits)
    for join in model.joins:
        tokens.update(join.emits)
    return tokens

def _mesh_closure_decision(findings: Sequence[MeshClosureFinding]) -> str:
    blocking = [finding for finding in findings if finding.severity in {'blocker', 'refactor'}]
    if not blocking:
        return 'mesh_closure_green'
    priority = ('missing_root_entry', 'unknown_closure_reference', 'loop_progress_required', 'loop_repeat_input_not_consumed',
        'loop_repair_feedback_required', 'loop_no_delta_disposition_required', 'loop_liveness_token_not_emitted',
        'unconsumed_child_output', 'unreachable_required_output', 'missing_join_point', 'terminal_leak', 'unreachable_normal_exit')
    codes = {finding.code for finding in blocking}
    for code in priority:
        if code in codes:
            return code
    return 'mesh_closure_blocked'

def review_mesh_closure_model(closure_model: MeshClosureModel) -> MeshClosureReport:
    """Review model-to-model handoff closure without expanding child internals."""
    findings: list[MeshClosureFinding] = []
    required_outputs = set(closure_model.required_outputs)
    consumed_tokens = _closure_consumed_tokens(closure_model)
    if not closure_model.root_entries:
        findings.append(MeshClosureFinding('missing_root_entry', 'mesh closure model has no parent entry token',
            model_id=closure_model.parent_model_id))
    known_tokens = _closure_known_tokens(closure_model)
    for token in sorted(consumed_tokens - known_tokens):
        findings.append(MeshClosureFinding('unknown_closure_reference', 'closure item consumes a token that is never produced or declared',
            model_id=closure_model.parent_model_id, item_id=token))
    for transition in closure_model.transitions:
        if transition.loop and (not transition.has_progress_rule()):
            findings.append(MeshClosureFinding('loop_progress_required', 'loop-like closure transition lacks a bound or progress rule',
                model_id=transition.consumer_model_id or closure_model.parent_model_id, item_id=transition.transition_id,
                metadata=transition.to_dict()))
        if transition.loop and transition.repeat_input_tokens:
            missing_repeat_inputs = tuple(sorted(set(transition.repeat_input_tokens) - set(transition.consumes)))
            if missing_repeat_inputs:
                findings.append(MeshClosureFinding('loop_repeat_input_not_consumed',
                    'repeat-input loop declares repeated tokens that the transition does not consume',
                    model_id=transition.consumer_model_id or closure_model.parent_model_id, item_id=transition.transition_id,
                    metadata={'missing_repeat_inputs': missing_repeat_inputs, 'transition': transition.to_dict()}))
            if not transition.repair_feedback_tokens:
                findings.append(MeshClosureFinding('loop_repair_feedback_required',
                    'repeat-input loop must emit structured repair feedback before retry can be safe',
                    model_id=transition.consumer_model_id or closure_model.parent_model_id, item_id=transition.transition_id,
                    metadata=transition.to_dict()))
            if not transition.has_structured_repeat_disposition():
                findings.append(MeshClosureFinding('loop_no_delta_disposition_required',
                    'repeat-input loop must declare a progress token, blocker token, or iteration bound',
                    model_id=transition.consumer_model_id or closure_model.parent_model_id, item_id=transition.transition_id,
                    metadata=transition.to_dict()))
            liveness_tokens = transition.progress_tokens + transition.repair_feedback_tokens + transition.blocker_tokens
            missing_emits = tuple(sorted(set(liveness_tokens) - set(transition.emits)))
            if missing_emits:
                findings.append(MeshClosureFinding('loop_liveness_token_not_emitted',
                    'repeat-input loop declares liveness tokens that are not emitted by the transition',
                    model_id=transition.consumer_model_id or closure_model.parent_model_id, item_id=transition.transition_id,
                    metadata={'missing_liveness_tokens': missing_emits, 'transition': transition.to_dict()}))
    for terminal in closure_model.terminals:
        if terminal.terminal_kind not in ALLOWED_MESH_CLOSURE_TERMINALS:
            findings.append(MeshClosureFinding('unknown_terminal_disposition', 'closure terminal uses an unknown disposition',
                model_id=closure_model.parent_model_id, item_id=terminal.terminal_id, metadata=terminal.to_dict()))
    for output in sorted(required_outputs - consumed_tokens):
        findings.append(MeshClosureFinding('unconsumed_child_output', 'required child or closure output has no declared consumer',
            model_id=closure_model.parent_model_id, item_id=output, metadata={'required_outputs': sorted(required_outputs)}))
    states: set[_ClosureState] = {_ClosureState(available=frozenset(closure_model.root_entries))}
    changed = True
    while changed:
        changed = False
        next_states = set(states)
        for state in states:
            if state.terminal_kind:
                continue
            for transition in closure_model.transitions:
                consumes = frozenset(transition.consumes)
                if consumes.issubset(state.available):
                    candidate = _ClosureState(available=state.available | frozenset(transition.emits), consumed=state.consumed | consumes,
                        completed_joins=state.completed_joins)
                    if candidate not in next_states:
                        next_states.add(candidate)
                        changed = True
            for join in closure_model.joins:
                required = frozenset(join.required_inputs)
                if required.issubset(state.available):
                    candidate = _ClosureState(available=state.available | frozenset(join.emits), consumed=state.consumed | required,
                        completed_joins=state.completed_joins | frozenset({join.join_id}))
                    if candidate not in next_states:
                        next_states.add(candidate)
                        changed = True
            for terminal in closure_model.terminals:
                consumes = frozenset(terminal.consumes)
                if consumes.issubset(state.available):
                    candidate = _ClosureState(available=state.available, consumed=state.consumed | consumes,
                        completed_joins=state.completed_joins, terminal_kind=terminal.terminal_kind)
                    if candidate not in next_states:
                        next_states.add(candidate)
                        changed = True
        states = next_states
    reachable_tokens = tuple(sorted({token for state in states for token in state.available}))
    reachable_required = set(reachable_tokens) & required_outputs
    for output in sorted(required_outputs - reachable_required):
        findings.append(MeshClosureFinding('unreachable_required_output',
            'required child or closure output is not reachable from a root entry', model_id=closure_model.parent_model_id, item_id=output,
            metadata={'reachable_tokens': reachable_tokens}))
    for join in closure_model.joins:
        if not any((join.join_id in state.completed_joins for state in states)):
            missing = tuple(sorted(set(join.required_inputs) - set(reachable_tokens)))
            findings.append(MeshClosureFinding('missing_join_point', 'required join point is not completed by reachable closure tokens',
                model_id=closure_model.parent_model_id, item_id=join.join_id, metadata={'join': join.to_dict(),
                'missing_inputs': missing}))
    terminal_states = [state for state in states if state.terminal_kind]
    for state in terminal_states:
        pending = tuple(sorted(required_outputs - set(state.consumed)))
        if pending:
            findings.append(MeshClosureFinding('terminal_leak', 'closure reaches a terminal disposition with pending required outputs',
                model_id=closure_model.parent_model_id, metadata={'terminal_kind': state.terminal_kind, 'pending_outputs': pending}))
    if closure_model.require_normal_exit and (not any((state.terminal_kind == MESH_CLOSURE_NORMAL_EXIT and (not required_outputs - set(state.consumed)) for state in terminal_states))):
        findings.append(MeshClosureFinding('unreachable_normal_exit',
            'closure model does not reach a normal exit with all required outputs consumed', model_id=closure_model.parent_model_id,
            metadata={'reachable_tokens': reachable_tokens}))
    decision = _mesh_closure_decision(findings)
    blocking = [finding for finding in findings if finding.severity in {'blocker', 'refactor'}]
    return MeshClosureReport(ok=not blocking, parent_model_id=closure_model.parent_model_id, decision=decision, findings=tuple(findings),
        reachable_tokens=reachable_tokens)

def closure_invariant(model: MeshClosureModel, name: str='handoffs_close') -> Invariant:
    """Bind the static handoff model to every reachable parent state."""
    report = review_mesh_closure_model(model)
    message = ', '.join((finding.code for finding in report.findings[:5]))

    def check(state, trace):
        return InvariantResult(report.ok, message if not report.ok else '')
    return Invariant(name, 'Required child handoffs close and reach their exits.', check)
__all__ = ['ALLOWED_MESH_CLOSURE_TERMINALS', 'MESH_CLOSURE_FAILURE_EXIT', 'MESH_CLOSURE_NORMAL_EXIT', 'MESH_CLOSURE_OUT_OF_SCOPE',
    'MESH_CLOSURE_TERMINAL_SIDE_EFFECT', 'MeshClosureFinding', 'MeshClosureJoin', 'MeshClosureModel', 'MeshClosureReport',
    'MeshClosureTerminal', 'MeshClosureTransition', 'closure_invariant', 'review_mesh_closure_model']
