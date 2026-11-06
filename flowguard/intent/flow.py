"""Small anchor graphs and scoped real readings; declarations are not a runner.

Only nodes, edges, finite state transitions and existing Rule relations live here.
The API/loader owns registration and the pytest plugin owns when a scope runs.
"""
from __future__ import annotations

from collections import Counter, deque
from dataclasses import dataclass, field as data_field
import dis
import inspect
from enum import Enum
from pathlib import Path
import sys

from .cells import Raised, same, kind_of
from ..map.common import content_digest


@dataclass(frozen=True)
class Node:
    name: str
    anchor: str = ''
    phase: str = 'call'
    occurrence: int | None = None
    start: bool = False
    end: bool = False
    model: object = None
    caller: str = ''

    @property
    def reference(self):
        return self.anchor or self.name


@dataclass(frozen=True)
class Transition:
    state: str
    before: object
    after: object
    on: str
    initial: bool = False


_UNSET = object()


@dataclass(frozen=True)
class Read:
    node: str
    field: str = 'result'
    occurrence: int | None = None
    view: str = ''
    equals: object = data_field(default=_UNSET, repr=False)

    def __post_init__(self):
        if self.view not in ('', 'utf8', 'empty'):
            raise ValueError('read view must be empty, strict lossless utf8, or container empty')
        if self.equals is not _UNSET and type(self.equals) not in (bool,int,float,str,bytes,type(None)):
            raise ValueError('equals needs a literal primitive; callbacks are unavailable')
        if not isinstance(self.field, str) or not self.field:
            raise ValueError('read needs a literal field path')
        if self.occurrence is not None and (type(self.occurrence) is not int or self.occurrence < 1):
            raise ValueError('read occurrence must be a positive integer')


@dataclass(frozen=True)
class Relation:
    rule: object
    inputs: dict[str, Read]
    actual: Read | None = None
    on: str = ''


@dataclass
class Flow:
    id: str
    source: str
    nodes: tuple
    edges: tuple
    transitions: tuple = ()
    relations: tuple = ()
    file: str = ''
    line: int = 0

    def __post_init__(self):
        self.nodes = tuple(n if isinstance(n, Node) else Node(n) for n in self.nodes)
        self.edges = tuple(tuple(e) for e in self.edges)
        self.transitions = tuple(t if isinstance(t, Transition) else Transition(*t) for t in self.transitions)
        self.relations = tuple(self.relations)

    @property
    def starts(self):
        return {n.name for n in self.nodes if n.start} or ({self.nodes[0].name} if self.nodes else set())

    @property
    def ends(self):
        return {n.name for n in self.nodes if n.end} or ({self.nodes[-1].name} if self.nodes else set())


@dataclass(frozen=True)
class Event:
    anchor: str
    phase: str
    values: dict = data_field(default_factory=dict)
    result: object = None
    error: BaseException | None = None
    case: str = ''
    occurrence: int = 1
    site: str = ''
    sequence: int = 0
    states: dict = data_field(default_factory=dict)
    before_states: dict = data_field(default_factory=dict)
    parents: tuple = ()
    caller: tuple = ()
    file: str = ''
    source_digest: str = ''


class Unverified(ValueError):
    pass


class _DomainError(ValueError):
    pass


def _result(kind, red=(), grey=(), info=(), **data):
    return dict(kind=kind, verdict='red' if red else 'grey' if grey else 'ok',
                red=list(dict.fromkeys(red)), grey=list(dict.fromkeys(grey)),
                info=list(dict.fromkeys(info)), **data)


def _rule(relation, rules):
    from .api import Rule
    rule = (rules or {}).get(relation.rule) if isinstance(relation.rule, str) else relation.rule
    if not isinstance(rule, Rule):
        raise Unverified(f'relation {relation.rule!r} does not reference an existing Rule')
    return rule


def validate(model, index, *, contracts=None):
    from .api import Rule
    red, grey, info = [], [], []
    names = [n.name for n in model.nodes]
    if not model.id or not model.source:
        red.append('flow needs an id and a sourced declaration')
    if not names or any(not isinstance(n,str) or not n for n in names) or len(names) != len(set(names)):
        red.append('flow needs nonempty, unique local node names')
    if len(names) > 10:
        info.append(f'{len(names)} nodes in one layer exceeds about 10; split at a real lower contract')
    for node in model.nodes:
        if node.phase not in {'call','return','raise'}:
            red.append(f'{node.name}: unsupported event phase {node.phase!r}')
        if node.caller:
            if node.caller not in names:
                red.append(f'{node.name}: caller must reference a node in this model')
            else:
                parent = next(n for n in model.nodes if n.name == node.caller)
                sites = index.named(parent.reference)
                if parent.phase != 'call' or not sites or not all(a.source_role == 'test' for a in sites):
                    grey.append(f'{node.name}: caller selector needs an explicit test-scenario call node')
        if node.occurrence is not None and (type(node.occurrence) is not int or node.occurrence < 1):
            red.append(f'{node.name}: occurrence needs a positive integer')
        if node.model is not None:
            if not isinstance(node.model, (str, Rule)):
                grey.append(f'{node.name}: recursive Flow export is unavailable; use a verified lower Rule')
            identifier = getattr(node.model, 'id', node.model)
            contract = (contracts or {}).get(identifier, {})
            if contract.get('verdict') != 'ok' or not contract.get('complete') or not contract.get('outcomes'):
                grey.append(f'{node.name}: lower model {identifier} has no verified finite output contract')
        anchors = index.named(node.reference)
        if not anchors:
            red.append(f'{node.name}: anchor gone: {node.reference}')
        for anchor in anchors:
            if anchor.kind not in {'event','sensor'}:
                red.append(f'{node.name}: {node.reference} is not a function observation anchor')
            for issue in anchor.issues:
                if issue.level == 'red': red.append(f'{node.name}: {issue.message}')
    referenced = {n.reference for n in model.nodes}
    for issue in index.issues:
        if issue.level == 'red' and issue.name in referenced:
            red.append(issue.message)
    for edge in model.edges:
        if len(edge) != 2 or any(n not in names for n in edge):
            red.append(f'edge references unknown nodes: {edge!r}')
    for item in model.transitions:
        if item.on not in names:
            red.append(f'transition references unknown node {item.on}')
        anchors = index.named(item.state, 'states')
        if not anchors:
            red.append(f'transition state anchor gone: {item.state}')
        for anchor in anchors:
            if item.before not in anchor.values or item.after not in anchor.values:
                red.append(f'{item.state}: transition {item.before!r} -> {item.after!r} is outside declared states')
    for rel in model.relations:
        if not isinstance(rel, Relation):
            red.append('relations must reference existing rules with literal reading bindings')
            continue
        if rel.on and rel.on not in names:
            red.append(f'relation references unknown trigger node {rel.on}')
        for read in [*rel.inputs.values(), *([rel.actual] if rel.actual else [])]:
            if not isinstance(read, Read):
                red.append('relation inputs and output must be literal Read bindings')
            elif read.node not in names and read.node != '$state':
                red.append(f'reading references unknown node {read.node}')
    return _result('flow-schema', red, grey, info)


def _expectation(rule, inputs, engine=None):
    if set(inputs) != set(rule.fields):
        raise _DomainError(f'{rule.id}: actual relation fields do not match declared fields')
    for name, spec in rule.fields.items():
        if not kind_of(spec).accepts(inputs[name]):
            raise _DomainError(f'{rule.id}: field {name} has actual type {type(inputs[name]).__name__}, outside declared {spec!r} domain')
    if engine is None:
        return rule.eval(inputs)
    from .engine import Engine, CONFLICT, PredicateError
    if not isinstance(engine, Engine):
        raise Unverified('effective rule evaluation requires the current Engine')
    expected = engine.effective(rule, inputs)
    if expected is CONFLICT:
        raise PredicateError(f'active rules conflict for {rule.decides} at {inputs!r}')
    return expected


def _current_rule(engine, reference):
    identifier = getattr(reference, 'id', reference)
    seen = set()
    while identifier in engine.m.superseded_by:
        if identifier in seen:
            raise Unverified(f'lower replacement cycle at {identifier}')
        seen.add(identifier)
        identifier = engine.m.superseded_by[identifier]
    return engine.m.rules.get(identifier)


def _state_relation(relation, state, rules, engine=None):
    rule = _rule(relation, rules)
    if any(r.node != '$state' for r in relation.inputs.values()) or relation.actual:
        return None
    inputs = {}
    for name, read in relation.inputs.items():
        if read.field not in state:
            raise Unverified(f'finite invariant reads unknown state {read.field}')
        inputs[name] = state[read.field]
    return rule.id, _expectation(rule,inputs,engine)


def finite_check(model, index, *, rules=None, contracts=None, max_states=4096, engine=None):
    rules = rules or (engine.m.rules if engine is not None and hasattr(engine, 'm') else {})
    schema = validate(model, index, contracts=contracts)
    red, grey, info = list(schema['red']), list(schema['grey']), list(schema['info'])
    if red:
        return _result('flow-finite', red, grey, info, states=0, reachable=[])
    initial = {}
    for transition in model.transitions:
        if transition.initial or transition.state not in initial:
            if transition.initial and transition.state in initial and initial[transition.state] != transition.before:
                explicit = [t.before for t in model.transitions if t.state == transition.state and t.initial]
                if len(set(explicit)) > 1:
                    red.append(f'{transition.state}: conflicting initial state declarations')
            initial[transition.state] = transition.before
    state_names = tuple(sorted(initial))
    outgoing = {n.name: [b for a,b in model.edges if a == n.name] for n in model.nodes}
    pending = deque((node, tuple(initial[s] for s in state_names)) for node in sorted(model.starts))
    seen, reached = set(), set()
    while pending:
        key = pending.popleft()
        if key in seen: continue
        if len(seen) >= max_states:
            grey.append(f'finite model exceeds {max_states} states; it was not exhausted')
            break
        seen.add(key); node, values = key; reached.add(node)
        state = dict(zip(state_names, values)); enabled = True
        changes = {}
        for state_name in {t.state for t in model.transitions if t.on == node}:
            options = [t for t in model.transitions if t.on == node and t.state == state_name and t.before == state[state_name]]
            if not options:
                red.append(f'{node}: no enabled transition for {state_name}={state[state_name]!r}')
                enabled = False
            elif len({t.after for t in options}) != 1:
                red.append(f'{node}: ambiguous transition for {state_name}={state[state_name]!r}')
                enabled = False
            else: changes[state_name] = options[0].after
        if not enabled: continue
        state.update(changes)
        for rel in model.relations:
            try:
                answer = _state_relation(rel, state, rules,engine)
                if answer and answer[1] is not None and answer[1] is not True:
                    red.append(f'finite invariant {answer[0]} fails at {node}: {state!r}')
            except Unverified as error: grey.append(str(error))
            except Exception as error: red.append(f'finite rule raised {type(error).__name__}: {error}')
        if not outgoing[node] and node not in model.ends:
            red.append(f'{node}: reachable dead end is not a declared terminal')
        values = tuple(state[s] for s in state_names)
        pending.extend((target, values) for target in outgoing[node])
    if not pending:
        red.extend(f'{node.name}: model node is unreachable' for node in model.nodes if node.name not in reached)
    return _result('flow-finite', red, grey, info, states=len(seen), reachable=sorted(reached),
                   exhausted=not pending and not any('not exhausted' in x for x in grey))


def _reading_event(read, readings, current=None):
    if read.node == '$state':
        if current is None:
            raise Unverified(f'state reading unavailable: {read.field}')
        return current
    candidates = readings.get(read.node, [])
    if read.occurrence is not None:
        candidates = [e for e in candidates if e.occurrence == read.occurrence]
    elif current is not None and any(e is current for e in candidates):
        candidates = [current]
    if len(candidates) != 1:
        raise Unverified(f'{read.node}: reading has {len(candidates)} occurrences; bind one explicitly')
    return candidates[0]


def _read(read, readings, current=None):
    if read.node == '$state':
        if current is None or read.field not in current.states:
            raise Unverified(f'state reading unavailable: {read.field}')
        value = current.states[read.field]
    else:
        event = _reading_event(read, readings, current)
        head, *parts = read.field.split('.')
        if head == 'arg':
            value = event.values
        elif head == 'result': value = event.result
        elif head == 'error': value = Raised(event.error) if event.error else None
        elif head == 'state':
            value = event.states
            name = '.'.join(parts)
            if name in value:
                value = value[name]; parts = []
        else: raise Unverified(f'unsupported reading field {read.field}')
        for part in parts:
            try:
                if isinstance(value, dict): value = value[part]
                elif isinstance(value, (tuple,list)) and part.isdigit(): value = value[int(part)]
                else: raise Unverified(f'{read.field}: no fixed data projection through {type(value).__name__}')
            except (KeyError,IndexError) as error:
                raise Unverified(f'{read.field}: fixed reading field missing') from error
    if isinstance(value, _Opaque):
        raise Unverified(f'unsupported declared reading type: {value.reason}')
    if read.view == 'utf8':
        if not isinstance(value, bytes):
            raise Unverified('utf8 view requires actual bytes')
        try: value = value.decode('utf-8')
        except UnicodeError as error: raise Unverified('actual bytes are not valid strict UTF-8') from error
    elif read.view == 'empty':
        if type(value) not in (list,tuple,dict):
            raise Unverified('empty view requires an actual list, tuple or dictionary')
        value = len(value) == 0
    if read.equals is not _UNSET:
        value = same(read.equals, value)
    return value


def _engine_contracts(model, engine, contracts, rules):
    """Reuse the existing contract/witness owner, never infer proof from a dict."""
    from .engine import Engine
    supplied = dict(contracts or {})
    red, grey = [], []
    needed = {getattr(n.model, 'id', n.model) for n in model.nodes if n.model is not None}
    for relation in model.relations:
        try:
            rule = _rule(relation, rules)
            if rule.uses:
                needed.add(rule.id)
            if isinstance(engine, Engine):
                needed.update(q.id for q in engine.m.active(rule.decides)
                              if q.uses and not engine.m.distinct_pair(rule.id,q.id))
        except Unverified as error:
            grey.append(str(error))
    if not needed:
        return supplied, red, grey
    if not isinstance(engine, Engine):
        grey.append('lower model outputs require the current Engine real contract and joint-witness checks; metadata alone is not verification')
        return supplied, red, grey
    for identifier in needed:
        if not isinstance(identifier, str) or identifier not in engine.m.rules:
            grey.append(f'{identifier}: recursive Flow export is unavailable; reference an existing lower Rule contract')
            continue
        try:
            current = _current_rule(engine,identifier)
            contract = supplied[identifier] = engine.contract_summary(current)
            supplied[current.id] = contract
            if contract['verdict'] == 'red':
                red.append(f'lower model {identifier}: real code contract is red')
                red.extend(f'{identifier}: {reason}' for key, value in engine.results.items()
                           if key[0] == current.id for reason in value.get('red', ()))
            elif contract['verdict'] != 'ok' or not contract.get('complete'):
                grey.append(f'lower model {identifier}: real contract is not a complete verified finite contract')
        except Exception as error:
            grey.append(f'{identifier}: real contract unavailable ({type(error).__name__}: {error})')
    return supplied, red, grey


def _lower_reading(node, event, engine, contracts):
    from .engine import Engine
    if node.model is None:
        return
    from .api import Rule
    if not isinstance(node.model, (str, Rule)):
        raise Unverified(f'{node.name}: recursive Flow export is not verified by a same-named Rule')
    identifier = getattr(node.model, 'id', node.model)
    if not isinstance(engine, Engine) or identifier not in engine.m.rules:
        raise Unverified(f'{node.name}: actual lower input has no current Engine witness verification')
    rule = _current_rule(engine,identifier)
    contract = contracts.get(identifier, {})
    if contract.get('verdict') != 'ok' or not contract.get('complete'):
        raise Unverified(f'{node.name}: lower output cannot be exported from an incomplete contract')
    if event.site not in set(contract.get('homes', ())) | set(contract.get('footprint', ())):
        raise Unverified(f'{node.name}: actual site {event.site} is outside the verified lower contract')
    if set(event.values) != set(rule.fields):
        raise Unverified(f'{node.name}: actual lower parameters do not uniquely match its declared fields')
    expected = _expectation(rule,event.values,engine)
    actual = Raised(event.error) if event.phase == 'raise' and event.error else event.result
    if expected is None:
        raise Unverified(f'{node.name}: lower rule has no opinion on the actual input')
    if not same(expected, actual):
        return f'{node.name}: actual lower result {actual!r} differs from its rule {expected!r}'
    witnesses = engine._verified_witnesses(rule, expected)
    if not any(all(same(inputs[k], event.values[k]) for k in inputs) for inputs in witnesses):
        raise Unverified(f'{node.name}: actual input is outside the verified lower representatives; no full-domain inference')


def _scenario_scopes(model, by_case, index):
    starts = [n for n in model.nodes if n.name in model.starts]
    test_start = {n.reference for n in starts if index.named(n.reference)
                  and all(a.source_role == 'test' for a in index.named(n.reference))}
    if not test_start:
        return by_case, 0
    scopes, ignored = {}, 0
    for case, events in by_case.items():
        beginnings = [e for e in events if e.anchor in test_start and e.phase == 'call']
        if not beginnings:
            ignored += 1
            continue
        for entry in beginnings:
            identity = entry.anchor, entry.site, entry.occurrence
            selected = [e for e in events if identity == (e.anchor,e.site,e.occurrence) or identity in e.parents]
            scopes[f'{case}/{entry.anchor}#{entry.occurrence}'] = selected
    return scopes, ignored


def _caller_matches(node, event, model, events, index):
    if not node.caller:
        return True
    caller_node = next(n for n in model.nodes if n.name == node.caller)
    if not index.named(caller_node.reference) or not all(a.source_role == 'test' for a in index.named(caller_node.reference)):
        return False  # This selector is only a declared experiment call edge.
    for parent in events:
        identity = parent.anchor,parent.site,parent.occurrence
        if (parent.anchor != caller_node.reference or parent.phase != 'call'
                or identity not in event.parents or not parent.file or len(event.caller) < 2):
            continue
        if event.caller[0] == parent.file and event.caller[1] == parent.site.partition(':')[2]:
            return True
    return False


def _group_cases(model, events, index):
    grey, info = [], []
    if isinstance(events, Capture):
        grey.extend(events.issues)
        events = events.events
    by_case, closed_cases, previous_case = {}, set(), None
    for event in events:
        if not isinstance(event, Event):
            grey.append('runtime input is not an anchor Event'); continue
        if previous_case is not None and previous_case != event.case:
            closed_cases.add(previous_case)
            if event.case in closed_cases:
                grey.append(f'{event.case}: case observations are interleaved; ordering is unverified')
        previous_case = event.case
        by_case.setdefault(event.case, []).append(event)
    by_case, ignored = _scenario_scopes(model, by_case, index)
    if ignored:
        info.append(f'{ignored} ordinary test scopes were outside this explicit scenario; no model verdict claimed for them')
    return by_case, ignored, grey, info


def _matching_nodes(model, event, case_events, index):
    return [n for n in model.nodes if n.reference == event.anchor and n.phase == event.phase
            and (n.occurrence is None or n.occurrence == event.occurrence)
            and _caller_matches(n,event,model,case_events,index)]


def _event_integrity(case, events):
    grey, pending, previous = [], set(), 0
    for event in events:
        if event.sequence <= previous:
            grey.append(f'{case}: event order is missing or nonmonotonic')
        previous = event.sequence
        call = event.anchor,event.site,event.occurrence
        if event.phase == 'call':
            if call in pending:
                grey.append(f'{case}: duplicate call occurrence {event.anchor}/{event.occurrence}')
            pending.add(call)
        elif event.phase in {'return','raise'}:
            if call not in pending:
                grey.append(f'{case}: {event.anchor} completion has no matching observed call')
            pending.discard(call)
        else: grey.append(f'{case}: unsupported runtime phase {event.phase}')
    if pending: grey.append(f'{case}: anchor invocations did not reach an observed return/raise')
    return grey


def runtime_check(model, events, index, *, rules=None, contracts=None, engine=None):
    rules = rules or (engine.m.rules if engine is not None and hasattr(engine, 'm') else {})
    contracts, bridge_red, bridge_grey = _engine_contracts(model, engine, contracts, rules)
    schema = validate(model, index, contracts=contracts)
    red, grey, info = list(schema['red'])+bridge_red, list(schema['grey'])+bridge_grey, list(schema['info'])
    edges, observed = set(model.edges), set()
    by_case, ignored, grouping_grey, grouping_info = _group_cases(model,events,index)
    grey.extend(grouping_grey); info.extend(grouping_info)
    order = list(by_case)
    checked, unclaimed = 0, 0
    observed_transitions = set()
    source_cache = {}
    for case in order:
        sequence, readings, case_events = [], {}, by_case[case]
        grey.extend(_event_integrity(case,case_events))
        caller_blocked, caller_accepted = set(), set()
        for candidate in case_events:
            for item in model.nodes:
                if item.reference == candidate.anchor and item.phase == candidate.phase and item.caller:
                    (caller_accepted if _caller_matches(item,candidate,model,case_events,index) else caller_blocked).add(item.name)
        uncertain_callers = caller_blocked - caller_accepted
        grey.extend(f'{case}: declared direct caller edge for {name} was not verified; helper extraction needs an explicit new binding'
                    for name in sorted(uncertain_callers))
        references = {n.reference for n in model.nodes}
        for event in case_events:
            if event.anchor not in references:
                info.append(f'anchor not included in {model.id}: {event.anchor}')
            nodes = _matching_nodes(model,event,case_events,index)
            if len(nodes) > 1:
                grey.append(f'{case}: {event.anchor} matches several model nodes; bind occurrence metadata'); continue
            if not nodes: continue
            node = nodes[0]
            try: _reading_source(event,index,Read(node.name),source_cache)
            except Unverified as error: grey.append(f'{case}: {error}')
            try:
                mismatch = _lower_reading(node, event, engine, contracts)
                if mismatch: red.append(f'{case}: {mismatch}')
            except Unverified as error: grey.append(f'{case}: {error}')
            except _DomainError as error: red.append(f'{case}: {error}')
            except Exception as error: grey.append(f'{case}: lower witness unavailable ({type(error).__name__}: {error})')
            if sequence:
                edge = sequence[-1], node.name
                if edge not in edges:
                    (grey if uncertain_callers else red).append(f'{case}: runtime path {edge[0]} -> {edge[1]} is not allowed'
                            + ('; declared caller edge is unverified' if uncertain_callers else ''))
                else: observed.add(edge)
            elif node.name not in model.starts:
                (grey if uncertain_callers else red).append(f'{case}: runtime starts at {node.name}, outside declared entries')
            sequence.append(node.name); readings.setdefault(node.name, []).append(event)
            modeled_states = {t.state for t in model.transitions}
            for state_name in modeled_states:
                expected = [t for t in model.transitions if t.on == node.name and t.state == state_name]
                before = event.before_states.get(state_name, _MISSING)
                after = event.states.get(state_name, _MISSING)
                if expected:
                    if event.phase != 'return' or before is _MISSING or after is _MISSING:
                        grey.append(f'{case}: {node.name} has no complete before/after reading for {state_name}')
                    elif not any(t.before == before and t.after == after for t in expected):
                        red.append(f'{case}: {state_name} actually changes {before!r} -> {after!r} at {node.name}, outside declared transitions')
                    else:
                        observed_transitions.add((state_name, before, after, node.name))
                elif before is not _MISSING and after is not _MISSING and before != after:
                    red.append(f'{case}: {state_name} changed at {node.name} without a declared transition')
            for rel in model.relations:
                if (rel.on or model.nodes[-1].name) != node.name: continue
                try:
                    rule = _rule(rel, rules)
                    inputs = {name: _read(read, readings, event) for name, read in rel.inputs.items()}
                    expected = _expectation(rule,inputs,engine)
                    if expected is None: unclaimed += 1; continue
                    actual = _read(rel.actual, readings, event) if rel.actual else True
                    checked += 1
                    if not same(expected, actual):
                        red.append(f'{case}: relation {rule.id} disagrees at {node.name}: expected {expected!r}, actual {actual!r}')
                except Unverified as error: grey.append(f'{case}: {error}')
                except Exception as error: red.append(f'{case}: relation raised {type(error).__name__}: {error}')
        if not sequence:
            grey.append(f'{case}: no model anchor was observed')
        elif sequence[-1] not in model.ends:
            (grey if uncertain_callers else red).append(f'{case}: runtime stopped at {sequence[-1]}, before a declared terminal')
    if not by_case: grey.append('no runtime anchor cases were observed')
    grey.extend(f'unobserved edge {a} -> {b}' for a,b in sorted(edges - observed))
    grey.extend(f'unobserved state transition {t.state}: {t.before!r} -> {t.after!r} at {t.on}'
                for t in model.transitions if (t.state,t.before,t.after,t.on) not in observed_transitions)
    if unclaimed: info.append(f'{unclaimed} readings were outside the original rules opinion')
    return _result('flow-runtime', red, grey, info, observed_edges=sorted(observed), cases=len(by_case),
                   checked_relations=checked, unclaimed_relations=unclaimed,
                   observed_transitions=sorted(observed_transitions,key=repr), ignored_case_scopes=ignored)


def _reading_source(observed, index, read, cache=None):
    sites = [a for a in index.named(observed.anchor) if a.target == observed.site]
    if len(sites) != 1 or not observed.file or not observed.source_digest:
        raise Unverified(f'{observed.anchor}: actual reading has no unique indexed source identity')
    anchor = sites[0]
    path = Path(observed.file)
    if cache is None:
        digest = content_digest(path) if path.is_file() else None
    else:
        if str(path) not in cache:
            cache[str(path)] = content_digest(path) if path.is_file() else None
        digest = cache[str(path)]
    if observed.source_digest != anchor.source_digest or digest != observed.source_digest:
        raise Unverified(f'{observed.anchor}: reading source identity changed; verify current source')
    return dict(anchor=observed.anchor,site=observed.site,file=observed.file,
                phase=observed.phase,occurrence=observed.occurrence,source_digest=observed.source_digest,
                field=read.field,view=read.view,equals_set=read.equals is not _UNSET,
                equals=read.equals if read.equals is not _UNSET else None)


def relation_observations(model, events, index, rule_id):
    """Read an actual decision outcome; never evaluate a Rule or invent output.

    This is the single projection used by calibrated scenario bindings. It does
    not run a scenario or verify its expectation. The existing Engine owns the
    subsequent rows/cells/mutation/joint checks. Multiple outputs stay ambiguous.
    """
    cases, ignored, grey, info = _group_cases(model,events,index)
    observations = []
    source_cache = {}
    if grey:
        return dict(status='grey',observations=[],grey=grey,info=info,ignored_case_scopes=ignored)
    for case, case_events in cases.items():
        integrity = _event_integrity(case,case_events)
        if integrity:
            grey.extend(integrity); continue
        readings, count = {}, 0
        for event in case_events:
            nodes = _matching_nodes(model,event,case_events,index)
            if len(nodes) > 1:
                grey.append(f'{case}: anchor matches several model nodes; reading is ambiguous')
                continue
            if not nodes: continue
            node = nodes[0]; readings.setdefault(node.name,[]).append(event)
            for position, relation in enumerate(model.relations):
                if getattr(relation.rule,'id',relation.rule) != rule_id:
                    continue
                if (relation.on or model.nodes[-1].name) != node.name:
                    continue
                if relation.actual is None:
                    grey.append(f'{case}: {rule_id} is an invariant without an actual decision reading')
                    continue
                try:
                    inputs = {name:_read(read,readings,event) for name,read in relation.inputs.items()}
                    actual = _read(relation.actual,readings,event)
                    sources = {}
                    for name,read in [*relation.inputs.items(),('$actual',relation.actual)]:
                        observed = _reading_event(read,readings,event)
                        sources[name] = _reading_source(observed,index,read,source_cache)
                    observations.append(dict(case=case,rule=rule_id,relation_index=position,
                                             inputs=inputs,actual=actual,sources=sources))
                    count += 1
                except Unverified as error: grey.append(f'{case}: {error}')
        if count > 1:
            grey.append(f'{case}: {rule_id} produced {count} actual readings; do not select first or last')
    if not observations:
        grey.append(f'{rule_id}: no complete actual relation reading was observed')
    return dict(status='grey' if grey else 'observed',observations=observations,
                grey=list(dict.fromkeys(grey)),info=info,ignored_case_scopes=ignored)


def static_check(model, report):
    red, grey, info = [], list(report.unknown), []
    edges = set(model.edges); supported_edges = set()
    for path in report.paths:
        local = []
        prefix = []
        for anchor in path:
            matches = [n for n in model.nodes if n.reference == anchor]
            if not matches:
                info.append(f'anchor not included in {model.id}: {anchor}')
                if not local: prefix.append(anchor)
                continue
            if len(matches) != 1:
                grey.append(f'{anchor}: static call path cannot choose phase/occurrence model node'); break
            local.append(matches[0].name)
        else:
            if local and prefix and local[0] not in model.starts:
                red.append(f'definite source bypass from new entry {prefix[0]} to {local[0]} outside declared entries')
            for edge in zip(local, local[1:]):
                if edge not in edges: red.append(f'definite source bypass {edge[0]} -> {edge[1]}')
                else: supported_edges.add(edge)
    grey.extend(f'model edge has no definite source path: {a} -> {b}' for a,b in sorted(edges-supported_edges))
    return _result('flow-static',red,grey,info,files=list(report.files))


def check_flow(model, index, events=(), *, rules=None, static=None, contracts=None, engine=None):
    rules = rules or (engine.m.rules if engine is not None and hasattr(engine, 'm') else {})
    contracts, _, _ = _engine_contracts(model, engine, contracts, rules)
    finite = finite_check(model, index, rules=rules, contracts=contracts,engine=engine)
    runtime = runtime_check(model, events, index, rules=rules,contracts=contracts,engine=engine)
    parts = [finite,runtime]
    if static is not None: parts.append(static_check(model,static))
    return _result('flow', [r for p in parts for r in p['red']], [r for p in parts for r in p['grey']],
                   [r for p in parts for r in p['info']], finite=finite,runtime=runtime,
                   provisional=any(c.get('provisional') for c in (contracts or {}).values()),
                   **({'static':parts[-1]} if static is not None else {}))


@dataclass(frozen=True)
class _Opaque:
    reason: str


def _snapshot(value, depth=0):
    if value is None or type(value) in (bool,int,float,str,bytes) or isinstance(value, Path): return value
    if isinstance(value, Enum):
        raw = object.__getattribute__(value, '__dict__').get('_value_', _MISSING)
        return value if type(raw) in (bool,int,float,str,bytes,type(None)) else _Opaque('enum value is not an immutable primitive')
    if depth < 6 and type(value) in (dict,list,tuple) and len(value) <= 1000:
        if isinstance(value,dict):
            if not all(type(k) in (str,int,bool) for k in value): return _Opaque('nonliteral mapping keys')
            return {k:_snapshot(v,depth+1) for k,v in value.items()}
        values = [_snapshot(v,depth+1) for v in value]
        return tuple(values) if type(value) is tuple else values
    return _Opaque(type(value).__name__)


_MISSING = object()


class Capture:
    """Observe only indexed function frames; the caller owns one actual test case.

    This does not call a project function, inject a case, infer success from entry,
    or turn an interrupted test into a pass. Values never survive this scope by
    themselves. Unsupported async/generator frames remain explicit unknowns.
    """
    def __init__(self, root, index, case):
        self.root, self.index, self.case = Path(root).resolve(), index, str(case)
        self.events, self.issues = [], []
        self._frames, self._counts, self._sites = {}, Counter(), {}
        for anchor in index.entries:
            if anchor.kind not in {'event','sensor'}: continue
            path = (self.root/anchor.file).resolve()
            if anchor.source_digest and (not path.is_file() or content_digest(path) != anchor.source_digest):
                self.issues.append(f'{anchor.name}: anchor source changed; rebuild the map'); continue
            self._sites.setdefault((str(path),anchor.qual),[]).append(anchor)
        self._trace = self._callback
        self._active = False

    def __enter__(self):
        if sys.gettrace() is not None:
            self.issues.append('another trace hook is active; anchor observation was not installed')
        else:
            sys.settrace(self._trace); self._active=True
        return self

    def __exit__(self, *error):
        if self._active:
            if sys.gettrace() is self._trace: sys.settrace(None)
            else: self.issues.append('trace hook changed during anchor observation')
            self._active = False
        for anchor in self.index.entries:
            path=self.root/anchor.file
            if anchor.source_digest and (not path.is_file() or content_digest(path)!=anchor.source_digest):
                self.issues.append(f'{anchor.name}: source changed during anchor observation')
        self._frames.clear()

    def on_trace(self, frame, event, arg):
        """One recorder for the calibration backend's existing trace hook.

        The backend delegates after replacing the target parameters and before
        its own terminal stop, then closes this recorder without installing a
        second hook. This method performs no injection or test execution.
        """
        return self._callback(frame,event,arg)

    def close(self):
        self.__exit__(None,None,None)

    def _states(self, frame, anchor):
        result = {}
        # Only explicitly declared class fields; never walk config objects or
        # call arbitrary getters. More than one actual instance is ambiguous.
        values = {id(value): value for value in frame.f_locals.values()}
        for state in self.index.entries:
            if state.kind != 'states': continue
            owner, _, name = state.qual.rpartition('.')
            matches = [value for value in values.values() if type(value).__module__ == state.module
                       and type(value).__qualname__.replace('.<locals>.','.') == owner]
            if len(matches) > 1:
                result[state.name] = _Opaque('several instances match declared state')
                self.issues.append(f'{state.name}: several actual instances match; state is unverified')
            elif matches:
                value = inspect.getattr_static(matches[0], name, _MISSING)
                if value is _MISSING:
                    result[state.name] = _Opaque('declared state has no literal runtime reading')
                else: result[state.name] = _snapshot(value)
        return result

    def _append(self, anchor, phase, args, occurrence, *, result=None,error=None,states=None,before=None,parents=(),caller=()):
        self.events.append(Event(anchor.name,phase,args,_snapshot(result),error,self.case,occurrence,
                                 anchor.target,len(self.events)+1,states or {},before or {},parents,caller,str((self.root/anchor.file).resolve()),anchor.source_digest))

    def _callback(self, frame, event, arg):
        key=id(frame)
        if event=='call':
            qual=frame.f_code.co_qualname.replace('.<locals>.','.')
            candidates=self._sites.get((frame.f_code.co_filename,qual),())
            if not candidates: return None
            if frame.f_code.co_flags & (inspect.CO_COROUTINE|inspect.CO_GENERATOR|inspect.CO_ASYNC_GENERATOR):
                self.issues.append(f'{qual}: async/generator anchor is not observed by this synchronous scope');return None
            selected=[a for a in candidates if a.line<=frame.f_code.co_firstlineno<=a.target_line]
            if len(selected)!=1:
                self.issues.append(f'{qual}: runtime source position does not identify one anchor');return None
            anchor=selected[0];self._counts[anchor.name]+=1;occurrence=self._counts[anchor.name]
            args={p.name:_snapshot(frame.f_locals.get(p.name,_Opaque('missing parameter')))for p in anchor.parameters}
            before=self._states(frame,anchor)
            parents=[];parent=frame.f_back
            caller=(parent.f_code.co_filename,parent.f_code.co_qualname.replace('.<locals>.','.'),parent.f_lineno)if parent else ()
            while parent is not None:
                found=self._frames.get(id(parent))
                if found: parents.append((found[0].name,found[0].target,found[2]))
                parent=parent.f_back
            parents=tuple(reversed(parents))
            self._frames[key]=[anchor,args,occurrence,None,before,parents,caller]
            self._append(anchor,'call',args,occurrence,states=before,before=before,parents=parents,caller=caller)
            return self._trace
        if key not in self._frames: return None
        state=self._frames[key]
        if event=='exception': state[3]=arg[1]
        if event=='return':
            anchor,args,occurrence,error,before,parents,caller=self._frames.pop(key)
            opcode=dis.opname[frame.f_code.co_code[frame.f_lasti]] if frame.f_lasti>=0 else ''
            failed=error is not None and opcode not in {'RETURN_VALUE','RETURN_CONST'}
            self._append(anchor,'raise' if failed else 'return',args,occurrence,result=arg,error=error if failed else None,
                         states=self._states(frame,anchor),before=before,parents=parents,caller=caller)
        return self._trace
