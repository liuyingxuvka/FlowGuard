"""Write-once decisions backed by the existing request and record owners.

Decisions settle requirement choices, not code conformance. Provisional decisions
stay open. STUCK/NEVER findings still require a real fix and complete exploration.
"""
from __future__ import annotations

from dataclasses import dataclass
import itertools
import json
from pathlib import Path
import re

from ..map.common import sha256_bytes
from ..map.mapfile import MapError
from ..map.records import integrity_problem, prepare_directory, write_once
from ..map.requests import REQUEST_DIR, _metadata, owner_quote, validate_request_links
from .model import State

DIRECTORY = Path('.flowguard/decisions')
_REPAIR = {'STUCK', 'NEVER REACHED', 'MASKING'}
_CONTRADICTIONS = {'CONTRADICTION', 'RULE CONTRADICTION'}


def _identity(entry):
    keys = ('id', 'kind', 'model', 'subject')
    if any(not isinstance(entry.get(key), str) or not entry[key] for key in keys):
        raise MapError('decision_conflict_invalid: conflict identity is missing')
    sources = entry.get('sources')
    if not isinstance(sources, list) or any(not isinstance(s, str) for s in sources):
        raise MapError('decision_conflict_invalid: sources must name stored requests')
    return {**{key: entry[key] for key in keys}, 'sources': sorted(set(sources))}


def _terms(entry):
    terms = entry.get('subject_terms')
    if not isinstance(terms, list) or not terms or any(not isinstance(t, str) or not t.strip() for t in terms):
        raise MapError('decision_subject_unknown: actual field/value/action/rule terms are unavailable')
    return sorted(set(terms))


def _drift(entry):
    return 'DRIFT' in entry['kind'].upper() or entry.get('code_status') == 'drift'


@dataclass(frozen=True)
class RuleContradiction:
    """Finite rule evaluation from a complete real graph, not an eligibility flag."""
    model: str
    rules: tuple[str, str]
    sources: tuple[str, str]
    condition: tuple
    rows: tuple[tuple[bool, bool], ...]
    universe: str = ''
    candidates: int = 0

    def to_dict(self):
        return dict(model=self.model, rules=list(self.rules), sources=list(self.sources),
                    condition=[list(v) for v in self.condition], rows=[list(v) for v in self.rows],
                    universe=self.universe, candidates=self.candidates)


def _no_rule_proof(message, required):
    if required:
        raise MapError(message)
    return None


def rule_contradiction(graph, rules, *, condition=None, required=True) -> RuleContradiction | None:
    """Prove two sourced always-rules cannot both hold in this finite condition.

    Each rule must separately be satisfiable. A capped graph, empty condition,
    failing predicate or two rules merely failing together proves no contradiction.
    Other rule forms remain unknown until their own computation supplies evidence.
    """
    if not graph.complete or graph.errors or graph.cut or graph.stopped_early:
        return _no_rule_proof('decision_rule_unknown: complete error-free graph required', required)
    if len(rules) != 2 or len(set(rules)) != 2:
        return _no_rule_proof('decision_rule_unknown: name two different rules', required)
    by_name = {r.name: r for r in graph.model.rules}
    selected = [by_name.get(name) for name in rules]
    if any(r is None or r.kind != 'always' or not r.source for r in selected):
        return _no_rule_proof('decision_rule_unknown: two sourced always-rules required', required)
    if selected[0].source == selected[1].source:
        return _no_rule_proof('decision_rule_unknown: two live requested obligations required', required)
    condition = condition or {}
    if any(key not in graph.keys for key in condition):
        return _no_rule_proof('decision_rule_unknown: condition names an unknown field', required)
    size = 1
    for field in graph.model.fields:
        size *= len(field.domain)
    if size > graph.max_states:
        return _no_rule_proof('decision_rule_unknown: declared candidate universe exceeds this computation budget', required)
    rows = []
    universe = []
    for values in itertools.product(*(field.domain for field in graph.model.fields)):
        state = State(zip(graph.keys, values))
        if any(state[key] != value for key, value in condition.items()):
            continue
        try:
            row = tuple(rule.pred(State(state)) for rule in selected)
        except Exception as error:
            from .model import ModelError
            raise ModelError(f'contradiction predicate failed: {type(error).__name__}: {error}') from error
        if any(type(value) is not bool for value in row):
            return _no_rule_proof('decision_rule_unknown: rule predicates must return bool', required)
        rows.append(row)
        from .descriptors import symbolic
        universe.append(repr(symbolic(dict(zip(graph.keys, values)), graph.model)))
    if not rows or any(all(row) for row in rows) or not all(any(row[i] for row in rows) for i in (0, 1)):
        return _no_rule_proof('decision_rules_not_contradictory: no finite contradictory pair established', required)
    return RuleContradiction(graph.model.name, tuple(rules), tuple(r.source for r in selected),
                             tuple(sorted(condition.items(), key=lambda v: repr(v[0]))), tuple(sorted(set(rows))),
                             sha256_bytes('\n'.join(sorted(universe)).encode()), len(universe))


def current_core(root, entry):
    """The current finished core through the existing result/cache owner."""
    from .project import read_conflicts
    from . import jobs
    data = read_conflicts(root) or {}
    recorded = data.get('models', {}).get(entry['model'], {}).get('core')
    if not isinstance(recorded, dict):
        raise MapError('provisional_evidence_missing: run check for a current finished computation')
    planned = jobs.Planned.from_json(recorded['planned'])
    part = jobs.lookup(root, planned)
    if part is None or part.digest != recorded['digest'] or not part.complete or not part.info.get('loaded'):
        raise MapError('provisional_evidence_stale: finish check on the current inputs')
    return part


def _provisional(root, entry, evidence):
    from .parts import PartResult
    if entry['kind'] not in _CONTRADICTIONS or _drift(entry):
        raise MapError('provisional_not_allowed: only two live requested rules contradicting each other qualify')
    if not isinstance(evidence, PartResult):
        raise MapError('provisional_evidence_missing: use the actual current finished core result, never caller-written rows')
    current = current_core(root, entry)
    if evidence.to_json() != current.to_json():
        raise MapError('provisional_evidence_stale: supplied result is not the current computation')
    proof = current.info.get('decision_evidence', {}).get(entry['id'])
    if not isinstance(proof, dict):
        raise MapError('provisional_not_allowed: this finding has no computed incompatible requested-rule pair')
    if proof['model'] != entry.get('model_name', entry['model']):
        raise MapError('provisional_evidence_mismatch: evidence belongs to another model')
    if len(set(proof['sources'])) != 2 or not set(proof['sources']) <= set(entry['sources']):
        raise MapError('provisional_evidence_mismatch: the conflict lacks both rule sources')
    validate_request_links(root, [dict(id=source, part=False) for source in proof['sources']])
    if any(_metadata(Path(root) / REQUEST_DIR / (source + '.json'), source)['kind'] != 'request'
           for source in proof['sources']):
        raise MapError('provisional_evidence_invalid: sources must be owner requests')
    if not set(proof['rules']) & set(_terms(entry)):
        raise MapError('provisional_evidence_mismatch: conflict does not name the evaluated rules')
    return proof


def _payload_id(payload):
    return 'D-' + sha256_bytes(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode())[:24]


def record_decision(root, entry, *, owner=None, request=None, provisional=None, evidence=None, purpose=None):
    """Persist one immutable event. No conflict, code or request is overwritten."""
    root = Path(root).resolve()
    identity = _identity(entry)
    if (owner is None) == (provisional is None):
        raise MapError('decision_mode_invalid: choose owner words or a provisional reason')
    if _drift(entry):
        raise MapError('decision_drift: repair model/code drift; it is not an owner conflict')
    payload = dict(version=1, conflict=identity, subject_terms=_terms(entry))
    if owner is not None:
        payload.update(mode='owner', authority=owner_quote(root, owner, payload['subject_terms'], request=request))
    else:
        if request is not None or not isinstance(provisional, str) or not provisional.strip():
            raise MapError('decision_mode_invalid: provisional reason must be nonempty')
        payload.update(mode='provisional', reason=provisional, evidence=_provisional(root, entry, evidence))
    if purpose is not None:
        if purpose != 'existing_routes' or owner is None or entry['kind'] != 'BOTH':
            raise MapError('decision_route_purpose_invalid: only an owner-authorized existing BOTH route qualifies')
        payload.update(purpose=purpose, route_evidence=_current_routes(root, entry))
    identifier = _payload_id(payload)
    event = dict(id=identifier, **payload)
    prepare_directory(root, DIRECTORY, ('.json',))
    relative = DIRECTORY / (identifier + '.json')
    write_once(root, relative, (json.dumps(event, sort_keys=True, ensure_ascii=False, indent=2) + '\n').encode())
    return event


def read_decision(root, identifier):
    if not isinstance(identifier, str) or not re.fullmatch(r'D-[0-9a-f]{24}', identifier):
        raise MapError('decision_id_invalid: use a stored decision id')
    relative = DIRECTORY / (identifier + '.json')
    problem = integrity_problem(root, relative)
    if problem:
        raise MapError('decision_edited: ' + problem)
    try:
        event = json.loads((Path(root) / relative).read_bytes())
        payload = {key: value for key, value in event.items() if key != 'id'}
        if event['id'] != identifier or _payload_id(payload) != identifier or event['version'] != 1:
            raise ValueError('identity/version differs')
        _identity(event['conflict'])
        _terms(event)
        if event.get('mode') == 'owner':
            if not isinstance(event.get('authority'), dict) or not {'id', 'quote', 'sha256', 'glossaries'} <= event['authority'].keys():
                raise ValueError('owner authority is missing')
            if 'purpose' in event and (event['purpose'] != 'existing_routes' or
                                      not isinstance(event.get('route_evidence'), dict)):
                raise ValueError('invalid existing-route purpose evidence')
        elif event.get('mode') == 'provisional':
            if not isinstance(event.get('reason'), str) or not event['reason'].strip() or not isinstance(event.get('evidence'), dict) or set(event['evidence']) != {'model', 'rules', 'sources', 'condition', 'rows', 'universe', 'candidates'}:
                raise ValueError('provisional evidence is missing')
        else:
            raise ValueError('unsupported decision mode')
    except (ValueError, KeyError, TypeError, AttributeError) as error:
        raise MapError(f'decision_invalid: {identifier}: {error}') from error
    return event


def _current_routes(root, entry, retained=None):
    """The native owner must have actually witnessed both current implementations."""
    from .codeaudit import is_entry, saved_result
    from .project import read_conflicts
    if entry['kind'] != 'BOTH' or not is_entry(entry):
        raise MapError('decision_routes_missing: a native BOTH finding is required')
    record = ({'digest': retained['receipt'], 'planned': retained['planned']} if retained is not None else
              (read_conflicts(root) or {}).get('code_audit'))
    result = saved_result(root, record)
    if result is None:
        raise MapError('decision_routes_stale: explicitly retest the current selected cases')
    row = next((raw for raw in result.findings if raw['id'] == entry['id']), None)
    route = row['detail']['route'] if row else {}
    if not route.get('primary') or not route.get('alternate') or route.get('classification') != 'BOTH':
        raise MapError('decision_routes_missing: both current routes need actual passing witnesses')
    return dict(receipt=result.digest, planned=record['planned'], subject=entry['subject'],
                primary=route['primary'], alternate=route['alternate'])


def decision_paths(event):
    """Immutable evidence that a commit using this decision must carry."""
    if event['mode'] == 'owner':
        requests = [event['authority']['id'], *(g['id'] for g in event['authority']['glossaries'])]
    else:
        requests = event['evidence']['sources']
    return sorted([(DIRECTORY / (event['id'] + '.json')).as_posix(),
                   *((REQUEST_DIR / (rid + suffix)).as_posix() for rid in set(requests) for suffix in ('.md', '.json'))])


def evaluate_decision(root, entry, identifier):
    """Revalidate current owner integrity/retirement and subject before applying."""
    event = read_decision(root, identifier)
    if event['conflict'] != _identity(entry) or event['subject_terms'] != _terms(entry) or _drift(entry):
        raise MapError('decision_conflict_changed: a different kind/subject/source needs its own decision')
    if event['mode'] == 'owner':
        old = event['authority']
        current = owner_quote(root, old['quote'], event['subject_terms'], request=old['id'])
        if current != old:
            raise MapError('decision_authority_changed: owner/glossary evidence changed')
        if event.get('purpose') == 'existing_routes':
            if _current_routes(root, entry, event['route_evidence']) != event['route_evidence']:
                raise MapError('decision_routes_changed: recheck the actual implemented route purpose')
            return dict(id=identifier, outcome='routes_declared', open=False, code_fixed=False,
                        commit_allowed=True, label='existing BOTH routes declared by live owner words')
        repair = ('model/code' if entry['kind'] in {'STUCK', 'NEVER REACHED'} and
                  (entry.get('native_confirmation') or {}).get('status') != 'confirmed' else 'code')
        return dict(id=identifier, outcome='owner_decided', open=True, code_fixed=False,
                    commit_allowed=entry['kind'] not in _REPAIR,
                    label=f'owner choice recorded; {repair} repair still required' if entry['kind'] in _REPAIR else 'owner decided')
    if event['mode'] != 'provisional':
        raise MapError('decision_invalid: unsupported decision mode')
    proof = _provisional(root, entry, current_core(root, entry))
    if proof != event['evidence']:
        raise MapError('provisional_evidence_changed: current requested-rule computation differs')
    return dict(id=identifier, outcome='provisional', open=True, code_fixed=False, commit_allowed=True,
                label='AI temporary decision, owner to confirm')
