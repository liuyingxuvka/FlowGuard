"""Source-bound requirement changes, derived by the existing history owner."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path

from ..map.common import MapError
from ..map.requests import REQUEST_DIR, _metadata, owner_quote, validate_request_links
from .decisions import decision_paths, evaluate_decision, read_decision

SCHEMA = 'flowguard.requirement-resolution.v1'
_OBLIGATION = {'sourced_obligation_removed', 'sourced_obligation_changed',
               'obligation_relation_unknown', 'sourced_obligation_weakened'}


def _chain(root, new, old, visiting=()):
    """Read every supersedes edge from the protected live request sidecars."""
    if new in visiting:
        return None
    validate_request_links(root, [dict(id=new, part=False)])
    metadata = _metadata(Path(root) / REQUEST_DIR / (new + '.json'), new)
    if metadata['kind'] != 'request':
        return None
    if new == old:
        return [new]
    for previous in metadata.get('supersedes', []):
        path = _chain(root, previous, old, (*visiting, new))
        if path is not None:
            return [new, *path]
    return None


def _coverage_rows(subject, before):
    key, separator, _ = subject.partition(': ')
    if not separator or key == 'anchors':
        return []
    if key.startswith('field:'):
        family = key.removeprefix('field:')
        return [row for row in before if row['kind'] == 'field' and family in row.get('terms', [])]
    if key in {'actions', 'rules'}:
        value = subject.partition(': ')[2]
        identity = ('operation:' + value) if key == 'actions' else ('rule:' + value)
        return [row for row in before if row['id'] == identity]
    if key.startswith('setting:'):
        return [row for row in before if row['id'] == key]
    return []


def derive(root, entry, current, reasons):
    """Return concrete authority only for all actual changed protections.

    This never executes a model and cannot waive a present STUCK/NEVER condition.
    Unknown original scope, deleted anchors, starts or object bounds stay unknown.
    The actual worker/native owner must still prove the resulting new behavior.
    """
    if (not current['finished'] or not current['loaded'] or not current['complete'] or current['errors']
            or 'conflicts' not in current or current['replay'] == 'reproduced'):
        return None
    if any(row['id'] == entry['id'] or (row['kind'], row['subject']) == (entry['kind'], entry['subject'])
           for row in current['conflicts']):
        return None
    baseline = entry.get('history', {}).get('baseline', {})
    before, after = baseline.get('obligations'), current['obligations']
    if before is None or after is None:
        return None
    old = {row['id']:row for row in before}
    now = {row['id']:row for row in after}
    affected = {}
    for reason in reasons:
        if reason['code'] in _OBLIGATION:
            rows = [old[reason['subject']]] if reason['subject'] in old else []
        elif reason['code'] == 'coverage_removed':
            rows = _coverage_rows(reason['subject'], before)
        else:
            return None
        if not rows or any(not row['sources'] or not row.get('terms') for row in rows):
            return None
        affected.update((row['id'], row) for row in rows)
    if not affected:
        return None
    events = []
    for identifier in entry.get('history', {}).get('decision_refs', []):
        try:
            event = read_decision(root, identifier)
            if event.get('mode') != 'owner' or event.get('purpose', 'owner_choice') != 'owner_choice':
                continue
            evaluate_decision(root, entry, identifier)
            events.append(event)
        except MapError:
            # The conflict keeps its reasons; status also exposes the invalid event.
            continue
    changes, paths = [], set()
    for identity, row in sorted(affected.items()):
        other = now.get(identity)
        selected = None
        for event in events:
            authority = event['authority']
            new = authority['id']
            if new in row['sources']:
                continue
            # A surviving declaration must bind the replacement request itself.
            # A retired declaration needs an implemented new sourced contract.
            replacement = ([other] if other is not None else
                           [candidate for candidate in after if candidate['kind'] in {'ending', 'field', 'operation', 'reach', 'always', 'progress'}])
            replacement = [candidate for candidate in replacement if new in candidate['sources']]
            if not replacement:
                continue
            try:
                relevant = owner_quote(root, authority['quote'], row['terms'], request=new)
                chains = [_chain(root, new, source) for source in row['sources']]
            except MapError:
                continue
            if not all(chains):
                continue
            selected = dict(obligation=identity, old=deepcopy(row), new=deepcopy(other),
                            replacement=[candidate['id'] for candidate in replacement],
                            decision=event['id'], authority=relevant, supersedes=chains)
            paths.update(decision_paths(event))
            for chain in chains:
                paths.update((REQUEST_DIR / (rid + suffix)).as_posix()
                             for rid in chain for suffix in ('.md', '.json'))
            for glossary in relevant['glossaries']:
                paths.update((REQUEST_DIR / (glossary['id'] + suffix)).as_posix() for suffix in ('.md', '.json'))
            break
        if selected is None:
            return None
        changes.append(selected)
    return dict(schema=SCHEMA, model_receipt=current['receipt'], changes=changes,
                scope=dict(before=deepcopy(baseline['scope']), after=deepcopy(current['scope']),
                           changes=deepcopy(reasons)), paths=sorted(paths),
                observation=deepcopy(current), boundary='requirement change; no code-fix claim')


def revalidate(root, entry, resolution):
    """Read-only authority check, also used by closed projections and staged policy."""
    from . import history
    if not isinstance(resolution, dict) or resolution.get('schema') != SCHEMA:
        raise MapError('requirement_resolution_invalid: missing source-bound resolution')
    try:
        current = history.observation(resolution['observation'])
        prior = history.assess(entry, current)
        actual = derive(root, entry, current, prior['reasons'])
    except (KeyError, history.HistoryError) as error:
        raise MapError('requirement_resolution_invalid: ' + str(error)) from error
    if actual != resolution:
        raise MapError('requirement_authority_changed: the live quote, supersedes relation or affected contract differs')
    return actual
