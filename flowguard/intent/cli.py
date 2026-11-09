"""A short screen and one pytest check route over generated structure and intent."""
from __future__ import annotations

import argparse
from contextlib import closing
import io
import json
import os
from pathlib import Path
import re
import shlex
import sys
import time
import tomllib

from flowguard import __version__
from flowguard.map.common import MapError
from flowguard.map.requests import owner_word, owner_words, retire_request, store_request
from flowguard.structure import build
from flowguard.structure.query import may_share, tokens
from . import cache
from .config import find_root, load_config


SENTINEL = '''"""Fail when declared FlowGuard intent was not collected."""
def test_flowguard_intent(request):
    from flowguard.intent.plugin import sentinel
    sentinel(request.config)
'''

PROJECT_RULES = '''<!-- flowguard:start -->
## FlowGuard rules for the project agent

1. Run ordinary tests with the FlowGuard plugin; read its changed outcomes, inconsistent copies and violated rules. Do not model the development task.
2. Before adding a judgment, use `python -m flowguard show "what it decides"` to find and reuse its existing owner.
3. Copies that must agree share a source sensor name. Requirements belong in independent rules; literal rows preserve genuine regressions. Unknown observations stay grey.
4. CI runs `check --all --deep`; local `check` selects affected tests. Preserve actual words only as a rule's source, once and byte for byte with `req add`.
<!-- flowguard:end -->
'''


def _limit(lines, budget):
    if len(lines) <= budget:
        return lines
    kept = lines[:max(0, budget - 1)]
    hidden = lines[len(kept):]
    reds = sum('red ' in line or line.startswith('red') for line in hidden)
    return kept + [f'... {len(hidden)} more lines ({reds} red): show RULE for the complete result']


def _kind(message):
    return 'tool' if message.startswith(('not mutable', 'not searched', 'not measured', 'unmapped', 'not exhaustive (budget')) else 'intent'


def _action(message):
    if '->' in message:
        return message
    if _kind(message) == 'tool':
        return message + ' -> tool: nothing to do here'
    return message + ' -> show the rule and correct its source, binding or regression rows'


def _rule_colour(item, result):
    if item.get('superseded_by'):
        return 'superseded'
    values = list(result.get('items', {}).values())
    if not values:
        return 'grey'
    if any(value.get('verdict') == 'red' for value in values):
        return 'red'
    if any(value.get('verdict') == 'grey' for value in values):
        return 'grey'
    return 'green*' if any(value.get('provisional') for value in values) else 'green'


def _test_name(nodeid):
    """Parameter IDs may contain ::, and the file path may contain brackets."""
    return nodeid.partition('::')[2].partition('[')[0].rsplit('::', 1)[-1]


def _map_notice(graph):
    coverage = graph.capabilities()
    foreign = {name: row for name, row in coverage.get('languages', {}).items() if name != 'python'}
    unsupported = coverage.get('unsupported_files', [])
    if not foreign and not unsupported:
        return ''
    parts = [f'{name} {row["parsed"]}/{row["files"]} parsed' for name, row in sorted(foreign.items())]
    if unsupported:
        parts.append(f'{len(unsupported)} unsupported source files (first: {unsupported[0]})')
    return 'Map: ' + '; '.join(parts) + '; static facts, foreign native-home execution not verified.'


def render(cfg, data, *, check=False, graph=None):
    summary = data['summary']
    rules = summary['rules']
    errors = summary['errors']
    load_results = [value for group in data['results'].values() for value in group.get('items', {}).values()
                    if value.get('kind') == 'load']
    attempt = data.get('attempt') or {}
    if not rules and not errors and not load_results and not attempt.get('errors'):
        return ['FlowGuard check: no intent rules.' if check else 'FlowGuard: no intent rules; show "what it decides" before adding another decision.']
    lines = [f'FlowGuard {__version__} {cfg.root.name}: {len(rules)} rules, '
             f'{sum(r.get("rows", 0) for r in rules.values())} rows; {summary["intent_lines"]} intent lines']
    if graph is not None:
        source_lines = graph.stats.get('source_lines', 0)
        ratio = 100 * summary['intent_lines'] / source_lines if source_lines else 0
        lines[0] += f'; {source_lines} source lines, intent {ratio:.1f}%'
        if notice := _map_notice(graph):
            lines.append(notice)
    red, grey, information, tool_causes = [], [], [], {}
    for error in errors:
        red.append(f'red load {error["file"]}:{error["line"]}: {error["msg"]} -> fix the intent file')
    for result in load_results:
        red.extend(f'red last check load: {message} -> correct the declaration and run check' for message in result.get('red', []))
    intent_attempt = attempt and (attempt.get('sentinel') is not None or attempt.get('collected')
                                  or attempt.get('selected') or attempt.get('deferred'))
    if intent_attempt and (attempt.get('missing') or attempt.get('sentinel') != 'ok'):
        red.append('red collection: declared intent or sentinel missing -> run init and collect the complete intent path')
    red.extend('red verification: ' + message for message in attempt.get('errors', []))
    red.extend('red ' + _action(message) for message in data.get('history', []))
    if data.get('check_scope'):
        information.append(data['check_scope'])
    information.extend(data.get('probes', []))
    colours = {}
    for rid, item in rules.items():
        result = data['results'].get(rid, {})
        colour = _rule_colour(item, result)
        colours[rid] = colour
        if colour == 'superseded':
            continue
        if not result.get('items'):
            grey.append(f'grey {rid}: no results yet -> run check')
        for value in result.get('items', {}).values():
            red.extend(f'red {rid}: {_action(message)}' for message in value.get('red', []))
            for message in value.get('grey', []):
                if _kind(message) == 'tool':
                    cause = message.split(':', 1)[0]
                    tool_causes.setdefault(cause, set()).add(rid)
                else:
                    grey.append(f'grey {rid}: {_action(message)}')
        if not check:
            information.append(f'{rid} {colour}: {item["decides"]}; {len(item.get("homes", []))} homes, {item.get("rows", 0)} rows')
    from .deps import test_scope
    current_test_scope = test_scope(cfg)
    for test, value in data.get('tests', {}).items():
        if not current_test_scope(test.partition('::')[0]):
            continue
        if value.get('outcome') == 'failed':
            line = f'{test}: {value.get("reason") or value.get("phase")} -> rerun this test after correcting the cause'
            (grey if value.get('kind') == 'env' else red).append(('grey env ' if value.get('kind') == 'env' else 'red test ') + line)
    for cause, rids in sorted(tool_causes.items()):
        grey.append(f'OPEN tool {cause}: {len(rids)} rules -> tool: nothing to do here; show RULE for details')
    counts = ', '.join(f'{sum(c == colour for c in colours.values())} {colour}' for colour in ('red', 'grey', 'green', 'green*'))
    lines.append(counts)
    lines.extend(dict.fromkeys(red))
    lines.extend(dict.fromkeys(grey))
    lines.extend(information)
    if not red and not grey:
        lines.append('No disagreement found in the checked rules and source anchors.')
    return _limit(lines, cfg.check_lines if check else cfg.screen_lines)


def _brief_source(cfg, item):
    """Only this rule's cited words, never the archive's conversation transcript."""
    from .sources import parse, authority
    from .api import IntentError
    from ..map.requests import quote_matches, read_request_bytes
    text = item.get('source', '')
    if not isinstance(text, str):
        return 'source unconfirmed'
    try:
        source = parse(text)
    except IntentError:
        return 'source unconfirmed'
    if source.kind == 'doc':
        valid, _ = authority(source, None, cfg, None)
        return ('source: ' + source.quote) if valid else 'source quote unconfirmed'
    if source.kind == 'owner':
        quote = item.get('quote') or source.text.partition(':')[2].strip()
        entry = owner_word(cfg.root, source.rids[0])
        if not entry or entry.get('edited') or entry.get('invalid') or entry.get('retired') or not isinstance(quote, str) or not quote:
            return 'owner source unconfirmed (no verified phrase)'
        text = read_request_bytes(cfg.root, source.rids[0]).decode('utf-8-sig')
        return (source.rids[0] + ': ' + quote) if quote_matches(text, quote) else 'owner quote unconfirmed'
    return source.kind + ' / unconfirmed'


def _brief(cfg, data, baseline):
    summary, candidates = data['summary'], []
    active = {rid: item for rid, item in summary['rules'].items() if not item.get('superseded_by')}
    for error in summary['errors']:
        candidates.append(f'red load {error["file"]}:{error["line"]}: {error["msg"]}')
    attempt = data.get('attempt') or {}
    candidates.extend('red verification: ' + message for message in attempt.get('errors', []))
    for rid, result in data['results'].items():
        for value in result.get('items', {}).values():
            if value.get('kind') == 'load':
                candidates.extend('red last check load: ' + message for message in value.get('red', []))
    pending = []
    for rid, item in active.items():
        result = data['results'].get(rid, {})
        colour = _rule_colour(item, result)
        if colour == 'red':
            messages = [message for value in result.get('items', {}).values() for message in value.get('red', [])]
            candidates.extend(f'red last check {rid}: ' + message for message in messages or ['reported red; show the complete result'])
            candidates.append(f'{rid} ' + _brief_source(cfg, item))
        elif colour in ('grey', 'green*'):
            pending.append(f'{rid}: ' + ('no results yet' if not result.get('items') else 'unfinished / unverified') + '; ' + _brief_source(cfg, item))
    from .deps import test_scope
    in_scope = test_scope(cfg)
    for test, reading in data.get('tests', {}).items():
        if reading.get('outcome') == 'failed' and in_scope(test.partition('::')[0]):
            candidates.append('red last check test ' + test + ': ' + (reading.get('reason') or reading.get('phase', 'failed')))
    if attempt.get('missing') or (attempt.get('collected') and attempt.get('sentinel') != 'ok'):
        candidates.append('red collection incomplete: run the complete check')
    if attempt.get('exit') not in (None, 0):
        pending.append(f'last check exit {attempt["exit"]}; task verification unfinished')
    candidates.extend('unfinished ' + line for line in pending)
    candidates = list(dict.fromkeys(candidates))
    reds = sum(line.startswith('red ') for line in candidates)
    header = f'FlowGuard: {len(active)} rules; {reds} red (parse / last check); baseline {baseline[:12] if baseline else "none (no Git commit)"}'
    if not active and not candidates:
        return [f'FlowGuard: no intent rules; baseline {baseline[:12] if baseline else "none (no Git commit)"}.']
    # A cached green is not a new verification. The brief reads no source map.
    lines = [header] + sorted(candidates, key=lambda line: not line.startswith('red '))
    lines = [line if len(line) <= 100 else line[:75] + '... (excerpt; show RULE)' for line in lines]
    budget = min(10, cfg.screen_lines)
    if len(lines) <= budget:
        return lines
    hidden = lines[budget - 1:]
    return lines[:budget - 1] + [f'... {len(hidden)} more lines ({sum(line.startswith("red ") for line in hidden)} red): show RULE for details']


def screen(cfg):
    from .health import brief_line
    baseline = cache.session_baseline(cfg, remember=True)
    data = cache.read(cfg)
    from .differences import display
    structure = brief_line(cfg)         # one line from the last check; the brief builds no map
    display('\n'.join([*_brief(cfg, data, baseline), *([structure] if structure else [])]))
    return int(bool(data['summary']['errors']))


def _candidate(candidate, full):
    if full:
        return json.dumps(candidate, ensure_ascii=False)
    return f'{candidate["id"]} {candidate.get("file", "")}:{candidate.get("line", "?")}: {candidate.get("reason", "source similarity only")}'


def _candidate_lines(found, full, prefix):
    candidates = found['candidates']
    visible = candidates if full else candidates[:3]
    result = [prefix + _candidate(candidate, full) + (' [线索]' if not full else '') for candidate in visible]
    if len(visible) < len(candidates):
        result.append(f'{len(candidates) - len(visible)} more source candidates; show --full for all pointers')
    return result


def _anchor_targets(index, references, graph=None):
    found = {}
    for reference in references:
        canonical = graph.canonical(reference) if graph is not None and ':' in reference else reference
        for anchor in index.entries:
            if reference == anchor.name or anchor.target in (reference, canonical):
                found[anchor.name, anchor.target, anchor.kind] = anchor
    return sorted(found.values(), key=lambda a: (a.name, a.file, a.target_line, a.kind))


def _source_pointers(index, references, graph, *, full=False):
    anchors = _anchor_targets(index, references, graph)
    lines = []
    for anchor in anchors:
        lines.append(f'anchor {anchor.name} -> {anchor.target} {anchor.file}:{anchor.target_line or anchor.line}'
                     + (f'; calibrated_by={anchor.calibrated_by}' if anchor.calibrated_by else ''))
        if full:
            lines.append(f'  {anchor.kind}; source comment L{anchor.line}; '
                         + ', '.join(f'{p.name}: {p.source_type} [{p.unit}]' for p in anchor.parameters))
    for reference in references:
        if reference.startswith('unresolved:'):
            lines.append('navigation unknown: ' + reference)
        elif not _anchor_targets(index, [reference], graph):
            lines.append(f'anchor {reference}: not found in the current source index')
    names = {a.name for a in anchors}
    issues = [i for i in index.issues if i.name in names] + [i for a in anchors for i in a.issues]
    lines.extend(dict.fromkeys(f'{issue.level} anchor {issue.name}: {issue.message}' for issue in issues))
    return anchors, lines


def _copy_pointers(graph, index, anchors, homes, summary, results, words, full, *, identifiers=()):
    excluded = set(homes) | {a.target for a in anchors}
    references = {a.name for a in anchors} | {a.target for a in anchors} | set(homes) | set(identifiers)
    for distinct in summary.get('distincts', []):
        if references & {distinct['a'], distinct['b']}:
            excluded.update(a.target for a in _anchor_targets(index, [distinct['a'], distinct['b']], graph))
            excluded.update(value for value in (distinct['a'], distinct['b']) if ':' in value)
            for value in (distinct['a'], distinct['b']):
                rule = summary['rules'].get(value, {})
                excluded.update(rule.get('homes', []))
                excluded.update(a.target for a in _anchor_targets(index, rule.get('anchors', []), graph))
    targets = list(dict.fromkeys([*homes, *(a.target for a in anchors
                 if a.source_role == 'production' and a.kind in {'sensor', 'event'})]))
    candidates, lines = {}, []
    for target in targets:
        live = next((result for result in results if result.get('target') == target and result.get('kind') == 'live'), None)
        scope = [(site.get('where') or target, site['line'], site['text']) for site in live.get('sites', []) if site.get('realized')] if live else None
        found = graph.search_homes(target, sites=scope, not_same=excluded, words=words, k=None)
        if not found['searched']:
            lines.append('copy search unavailable: ' + found.get('reason', 'no readable decision sites'))
        from .owners import look_alikes      # static copy candidates, the same ones check runs for an owner
        registered = {a.target for a in index.entries if a.kind == 'sensor'}
        for candidate in [*found['candidates'], *look_alikes(load_config(graph.root), graph, target, excluded | registered)]:
            node = graph.node(candidate['id'])
            if node:
                candidate = dict(candidate, file=node['file'], line=node['line'])
            old = candidates.get(candidate['id'])
            rank = lambda row: (row.get('strength') == 'strong', row.get('score', 0))   # a site match over a look-alike
            if old is None or rank(candidate) > rank(old):
                candidates[candidate['id']] = candidate
    found = dict(candidates=sorted(candidates.values(), key=lambda row: (-row.get('score', 0), row['id'])))
    return list(dict.fromkeys(lines)) + _candidate_lines(found, full, '线索 unbound candidate ')


def _unmodelled(index, summary, *, root=None):
    references = {ref for item in summary['rules'].values() for ref in item.get('anchors', [])}
    references.update(value for relation in summary.get('distincts', []) for value in (relation['a'], relation['b']))
    def identity(anchor):
        return (anchor.name, anchor.target, anchor.file, anchor.source_digest,
                anchor.kind, anchor.target_line, anchor.parameters)
    used = {identity(a) for a in _anchor_targets(index, references)}
    return sorted({a.name for a in index.entries if a.source_role == 'production' and identity(a) not in used})


def _observation_lines(cfg, graph, data, node):
    return ['source navigation: current Map identity; runtime readings are historical and available for declared anchors']


def _silent_lines(cfg, index, rid, full, limit=10):
    """The case classes a rule gives no result for, from the current rules (never the code). Where no rule
    of its decision decides and a rule there says total=True, they are red."""
    from .engine import Engine
    from .loader import load
    model = load(cfg, anchor_index=index)
    if model.errors or rid not in model.rules:
        return []           # the load errors are printed by show and the load item
    rule = model.rules[rid]
    key = Engine(model).check_key(rule.decides)
    silent, gaps = key['silent'].get(rid, []), key['gaps'] or {}
    if not silent:
        return []
    def listed(values):
        shown = values if full else values[:limit]
        return '；'.join(shown) + (f'；另 {len(values) - len(shown)} 类：show --full {rid} 列出全部' if len(shown) < len(values) else '')
    lines = [f'没表态：规则 {rid} 对 {len(silent)} 类情况没有给出结果（共 {key["cells"]} 类）：{listed(silent)}']
    undecided = [cell for cell in gaps.get('cells', ()) if cell in silent]
    if undecided and gaps.get('total'):
        lines.append(f'红：{"、".join(gaps["total"])} 写了 total=True，{len(undecided)} 类情况没有任何规则表态：{listed(undecided)}'
                     f' -> 在规则里给出这些情况的结果，或去掉 total=True')
    elif undecided and len(undecided) < len(silent):
        lines.append(f'其中 {len(undecided)} 类也没有别的规则表态：{listed(undecided)}')
    return lines


def show(cfg, query=None, *, draft=None, gaps=None, full=False):
    query = draft or query
    if not gaps and query:
        request = cfg.root / '.flowguard/requests' / (query + '.md')
        if request.is_file():
            row = owner_word(cfg.root, query)
            if row and not row.get('edited') and not row.get('invalid'):
                if row.get('retired'):
                    print(f'RETIRED {query}: not the owner\'s words; original bytes remain in the archive.')
                    return 0
                print(f'OWNER {query}\n' + request.read_bytes().decode('utf-8-sig'))
                return 0
            raise ValueError(f'{query}: stored original is not verified')
    data = cache.read(cfg)
    rules = data['summary']['rules']
    if gaps:
        from .engine import Engine
        from .loader import load
        model = load(cfg)
        if gaps not in model.keys():
            raise ValueError(f'unknown decision key {gaps}')
        result = Engine(model).check_key(gaps)
        print(json.dumps(result.get('gaps') or {'gaps': 0}, ensure_ascii=False))
        return 0
    if not query:
        raise ValueError('show needs a rule, function, request id or words')
    errors = [e for e in data['summary']['errors']
              if (query in rules and e['file'] == rules[query]['file'])
              or query in (cfg.root / e['file']).read_text(encoding='utf-8-sig')]
    if errors:
        for error in errors:
            print(f'red load {error["file"]}:{error["line"]}: {error["msg"]} -> fix the intent file')
        return 1
    with closing(build(cfg.root, roots=cfg.roots)) as graph:
        from .anchors import collect
        index = collect(graph)
        notice = _map_notice(graph)
        if query in rules and rules[query].get('kind') == 'flow' and not draft:
            from .debug import show_observation
            _, pointers = _source_pointers(index, rules[query].get('anchors', ()), graph, full=full)
            view = show_observation(cfg, query, index, cache.observations(cfg).get('events', ()))
            print('\n'.join([*pointers, *view['lines']]))
            return int(view['status'] == 'red')
        if query in rules:
            item = rules[query]
            lines = [f'RULE {query}: {item["decides"]}', item.get('doc', '') if full else '', f'source: {item["source"]}',
                     f'{item["file"]}:{item["line"]}; {item.get("rows", 0)} literal rows']
            if notice:
                lines.insert(1, notice)
            for home in item.get('homes', []) if item.get('kind') == 'rule' else []:
                lines.append('home ' + home)
                if full:
                    lines.extend(f'  site L{s["line"]}: {s["field"]} {s["op"]} {s["const"]}' for s in graph.sites(home))
            for result in data['results'].get(query, {}).get('items', {}).values():
                lines.extend(result.get('red', []) + result.get('grey', []) + (result.get('info', []) if full else []))
            if item.get('kind') == 'rule':
                lines.extend(_silent_lines(cfg, index, query, full))
            anchors, pointers = _source_pointers(index, item.get('anchors', []), graph, full=full)
            lines.extend(pointers)
            if item.get('flows'):lines.append('via flow ' + ', '.join(dict.fromkeys(item['flows'])))
            lines.extend('navigation unknown: ' + value for value in item.get('navigation_unknown', []))
            lines.extend(_copy_pointers(graph, index, anchors, item.get('homes', []), data['summary'],
                         list(data['results'].get(query, {}).get('items', {}).values()),
                         item.get('doc', '') + ' ' + item['decides'], full, identifiers=(query,)))
            from .deps import Now, stale
            if data['results'].get(query) and (not data['deps'].get(query) or stale(data['deps'][query], Now(cfg, graph))):
                lines.insert(1, 'cached results are stale or unverified -> run check')
            from .differences import display      # copy pointers carry project names: escape what the console cannot show
            display('\n'.join(line for line in lines if line))
            return int(bool(data['summary']['errors']))
        if data['summary']['errors'] and any(query in (cfg.root / e['file']).read_text(encoding='utf-8-sig') for e in data['summary']['errors']):
            for error in data['summary']['errors']:
                print(f'red load {error["file"]}:{error["line"]}: {error["msg"]} -> fix the intent file')
            return 1
        anchors, pointers = _source_pointers(index, [query], graph, full=full)
        if anchors:
            print('ANCHOR ' + query)
            print('\n'.join(pointers))
            from .owners import show_lines     # an owner's old ledger: writes outside its writers, look-alikes
            if owned := show_lines(cfg, graph, index, query):
                from .differences import display
                display('\n'.join(owned))
            from .debug import show_observation
            from types import SimpleNamespace
            model = SimpleNamespace(rules={rid: SimpleNamespace(id=rid, anchors=value.get('anchors', ()))
                                         for rid, value in rules.items()})
            view = show_observation(cfg, query, index, cache.observations(cfg).get('events', ()), model=model)
            print('\n'.join(view['lines']))
            if draft:
                seen = set()
                for anchor in anchors:
                    node = graph.node(graph.canonical(anchor.target) or anchor.target)
                    if node and node['id'] not in seen:
                        seen.add(node['id'])
                        print('\n'.join(_observation_lines(cfg, graph, data, node)))
            unused = set(_unmodelled(index, data['summary'], root=cfg.root)) & {a.name for a in anchors}
            if unused:print('info: not referenced by a current model: ' + ', '.join(sorted(unused)))
            from .differences import display
            display('\n'.join(_copy_pointers(graph, index, anchors, [], data['summary'], [], query, full)))
            return 0
        node = graph.node(graph.canonical(query) or query)
        if node:
            print(f'{query} {node["file"]}:{node["line"]}\n{node["sig"]}\n{node["doc"]}')
            if notice:
                print(notice)
            if draft and node.get('language', 'python') != 'python':
                print('Static source only: this language has no verified native-home execution adapter.')
                return 0
            if draft:
                print('use anchor draft for a source comment; impure code needs an ordinary calibration test')
                print('\n'.join(_observation_lines(cfg, graph, data, node)))
            else:
                found = graph.search_homes(query, k=None)
                if not found['searched']:
                    print('not searched: ' + found.get('reason', '') + ' -> bind the real decision site')
                print('\n'.join(_candidate_lines(found, full, 'candidate ')))
            return 0
        words = tokens(query)
        ranked = []
        if re.fullmatch(r'[A-Za-z_]\w*\.[A-Za-z_]\w*', query):      # Model.field or table.column: who writes it
            written = graph.writes(query)
            for row in written:
                where = f'{row["file"]}:{row["line"]}' + (f' (call line {row["call_line"]})' if row['call_line'] != row['line'] else '')
                unclear = f'; unclear: {row["reason"]}' if row['unclear'] else ''
                ranked.append((2000 - bool(row['unclear']), f'writes {row["model"] or row["table"]}.{row["field"]} '
                               f'{where} {row["function"]} ({row["kind"]}{unclear})'))
            from . import health, owners as checks       # several files write it and nobody owns it: say so first
            for issue in health.writers(checks.Change(cfg, graph, None), index, written).issues:
                ranked.append((2001, f'structure: {issue.text} -> {issue.step} ' + ' '.join(issue.entry)))
        for rid, rule in rules.items():
            score = 1000 if query.casefold() in {rid.casefold(), rule['decides'].casefold()} else 0
            score += 4 * len(words & tokens(rule['decides'] + ' ' + rule.get('doc', '')))
            if score:
                ranked.append((score, f'rule {rid}: {rule["decides"]} {rule.get("doc", "")}'))
        owners = graph.outline(('function', 'method', 'class'))
        decided = {}
        for node, field, identity in graph.con.execute('SELECT node, field, identity FROM site'):
            decided.setdefault(node, []).append((field or '') + ' ' + (identity or ''))
        for ident, item in owners.items():
            names = {ident.casefold(), item['qual'].casefold(), item['qual'].rsplit('.', 1)[-1].casefold()}
            score = 1000 if query.casefold() in names else 0
            # Only an owner whose text can hold a query word is split into words (may_share is exact).
            if any(may_share(words, text) for text in decided.get(ident, ())):
                sites = graph.sites(ident)
                score += 2 * len(words & tokens(' '.join(s['field'] + ' ' + (s['identity'] or '') for s in sites)))
            if may_share(words, ident + ' ' + item['doc']):
                score += len(words & tokens(ident + ' ' + item['doc']))
            if score:
                ranked.append((score, f'{ident} {item["file"]}:{item["line"]}'))
        for ident, aliases in graph.import_aliases(query).items():       # the names an import binds to an owner
            item = graph.node(ident)
            ranked.extend((1000, f'{alias} -> {ident} {item["file"]}:{item["line"]}') for alias in aliases)
        ranked.sort(key=lambda row: (-row[0], row[1]))
        from .differences import display          # a structure line carries Chinese text: escape what the console cannot show
        display('\n'.join(_limit([f'show {query}'] + ([notice] if notice else [])
                                 + [line for _, line in ranked], cfg.screen_lines)))
    return 0


def draft_anchor(cfg, target):
    from .anchors import draft
    with closing(build(cfg.root, roots=cfg.roots)) as graph:
        result = draft(graph, graph.canonical(target) or target)
    if result.text:
        print(result.text)
    for name, points in result.ranges.get('points', {}).items():
        print(f'range {name}: {points!r}')
    if result.ranges:
        print(f'{result.ranges["total"]} representative cells; complete={result.ranges["complete"]}')
    for issue in result.issues:
        print(f'{issue.level} {issue.file}:{issue.line}: {issue.message}')
    return int(result.status == 'red')


def draft_model(cfg, name):
    from .debug import _events, _index
    from .flow import draft_model as from_events, template_lines
    events = _events(cache.observations(cfg).get('events', ()))
    result = from_events(name, _index(cfg), events)
    for note in result.notes:
        print('# grey: ' + note)
    if result.model is not None:
        model = result.model
        print('from flowguard.intent import flow, Node')
        print(f'MODEL = flow({model.id!r}, source={model.source!r}, nodes={model.nodes!r}, edges={model.edges!r})')
    lines = template_lines(events)
    if lines:
        print('# one-line templates from observed paths, grouped by flow; keep, tighten (guarded_by, checks) or delete each')
        print('from flowguard.intent import precedes, transitions')
        for flow in dict.fromkeys(row['flow'] for row in lines):
            members = [row for row in lines if row['flow'] == flow]
            print(f'# flow {flow} ({members[0]["tests"]} tests)')
            print('\n'.join(row['text'] for row in members))
    return 0


def try_anchor(cfg, name, assignments, *, grid=False):
    import ast
    from . import debug
    values = {}
    for assignment in assignments:
        key, separator, value = assignment.partition('=')
        if not separator or not key.isidentifier() or key in values:
            raise ValueError('try inputs must be unique name=literal assignments')
        try:
            values[key] = ast.literal_eval(value)
        except (ValueError, SyntaxError) as error:
            raise ValueError(f'{key}: use a Python literal value') from error
    result = debug.try_anchor(cfg, name, values, grid=grid, runner=debug.try_in_test)
    print('\n'.join(result['lines']))
    return {'ok': 0, 'red': 1, 'grey': 2}[result['status']]


def watch(cfg, command):
    from . import debug
    command = command[1:] if command[:1] == ['--'] else command
    result = debug.watch(cfg, command)
    if result.get('executed'):
        debug.save_observation(cfg, result['events'])
    print('\n'.join(result['lines']))
    return result['exit_code'] or int(result['status'] == 'red')






def check(cfg, *, everything=False, since=None, deep=False, base=None):
    """Run the one ordinary pytest route; source validation executes no code."""
    from .plugin import collect_signals
    from .signals import render as render_signals
    with collect_signals() as reports:
        status = _check(cfg, everything=everything, since=since, deep=deep, base=base, reports=reports)
    from .differences import _source_index, _compare_pairs
    index = _source_index(cfg.root)
    issues = [issue for issue in index.issues if issue.level == 'red']
    # A reached but unsafe sensor keeps its actual grey context. Only unvisited
    # copies may use check's existing, source-verified pure-function exception.
    observed = {item.get('name') for part in reports for item in part.get('items', ()) if item.get('file')}
    for name in sorted({anchor.name for anchor in index.entries if anchor.kind == 'sensor'} - observed):
        # A function owner is the reference its same-name copies are compared with.
        copies = sorted((anchor for anchor in index.named(name, 'sensor') if anchor.source_role == 'production'),
                        key=lambda anchor: not anchor.owner)
        if len(copies) < 2:
            continue
        compared = _compare_pairs(cfg.root, [(copies[0], other) for other in copies[1:]])
        items = compared['items'] or [dict(name=name, status=compared['status'], reasons=compared['reasons'], complete=False)]
        reports.append(dict(source_changed=compared['status'] != 'ok',
                            items=[dict(item, comparison=True, same_name=True) for item in items],
                            red=compared['reasons'] if compared['status'] == 'red' and not compared['changes'] else []))
        status = status or int(compared['status'] == 'red')
    found = _owner_findings(cfg, everything=everything, base=base)
    if found.red or found.leads or found.section:
        reports.append(dict(source_changed=True, red=found.red, leads=found.leads, items=[], structure=found.section))
        status = status or int(bool(found.red))
    baseline = next((part for part in reports if part.get('baseline')), {})
    ledger_red = []
    for finding in (finding for part in reports for finding in part.get('ledger_red', ())):
        if finding not in ledger_red:
            ledger_red.append(finding)
    red = []
    for message in (*(message for part in reports for message in part.get('red', ())),
                    *(f'{issue.file}:{issue.line}: {issue.message}' for issue in issues)):
        # One red per finding: the same text from two batches, also with an ASCII colon, prints once.
        if not any(message.replace('：', ': ') == seen.replace('：', ': ') for seen in red):
            red.append(message)
    report = dict(session=True, baseline=baseline.get('baseline'), baseline_kind=baseline.get('baseline_kind', 'task'),
                  source_changed=any(part.get('source_changed', True) for part in reports),
                  comparison_requested=any(part.get('comparison_requested') for part in reports),
                  items=[item for part in reports for item in part.get('items', ())],
                  paths=[path for part in reports for path in part.get('paths', ())],
                  leads=[lead for part in reports for lead in part.get('leads', ())],
                  unverified=[line for part in reports for line in part.get('unverified', ())],
                  red=red, ledger_red=ledger_red,
                  steps={subject: lines for part in reversed(reports) for subject, lines in part.get('steps', {}).items()},
                  structure=[line for part in reports for line in part.get('structure', ())])
    _show_signals(render_signals(report), status)
    return status or int(bool(issues))


def _show_signals(text, status):
    """The signal report on the console, as at the end of an ordinary test run."""
    if text:
        try:
            from .differences import display
            display(text)
        except BrokenPipeError:
            raise           # A closed consumer is quiet at the command entry, not an unavailable output.
        except (OSError, ValueError) as error:
            try:
                print(f'FlowGuard output unavailable: {type(error).__name__}; verification status {status}', file=sys.stderr)
            except (OSError, ValueError):
                pass


def static_check(cfg, *, everything=False, base=None):
    """`check --static`: the map checks alone, without pytest: the fallback ledger, owner writes and pairs,
    values outside declared sets, old values, new spellings, unchanged copies, deletes that leave children,
    missing columns and touched structure problems. The report is rendered as at the end of an ordinary
    test run; only what this change adds is reported unless `everything` (`--all`), which also lists every
    open structure problem. Exit 1 when anything is red."""
    from . import anchors, health, ledger as fallbacks, owners
    from .signals import render as render_signals
    with closing(build(cfg.root, roots=cfg.roots)) as graph:
        index = anchors.collect(graph)
        found = owners.static_findings(cfg, graph, index, base, everything=everything)
        baseline = owners.baseline(cfg, base)
        result = fallbacks.evaluate(cfg, graph, baseline=baseline) if fallbacks.path(cfg).is_file() \
            else fallbacks.absent(cfg, baseline)
        with graph.con:
            cache.save_structure(graph.con, found.summary)
    red = list(dict.fromkeys([*found.red, *(issue.message for issue in index.issues if issue.level == 'red')]))
    report = dict(session=True, baseline=baseline, baseline_kind='base' if base else 'task',
                  source_changed=bool(red or found.leads or found.section or result.red), red=red, leads=found.leads,
                  items=[], ledger_red=[dict(text=finding.text, fix=list(finding.fix)) for finding in result.red],
                  structure=found.section)
    status = int(bool(red or result.red))
    _show_signals(render_signals(report), status)
    return status


def _owner_findings(cfg, *, everything=False, base=None):
    """Owners, copies and static leads of this change; copy discovery runs only here, in check."""
    from . import anchors, owners
    if not owners.baseline(cfg, base) and not everything:
        return owners.Findings()            # nothing is new without a baseline; the old ledger is check --all
    with closing(build(cfg.root, roots=cfg.roots)) as graph:
        index = anchors.collect(graph)
        distincts = cache.read(cfg)['summary'].get('distincts', [])
        excluded = {target for item in distincts for target in (item['a'], item['b']) if ':' in target}
        excluded |= {anchor.target for item in distincts for name in (item['a'], item['b']) for anchor in index.named(name)}
        found = owners.check_findings(cfg, graph, index, base, everything=everything, excluded=excluded)
        with graph.con:
            cache.save_structure(graph.con, found.summary)
        return found


def _check_selection(cfg: Config, model: object, data: dict, everything: bool, since: str | None, sentinel: Path):
    import ast
    from . import deps, history
    with closing(build(cfg.root, roots=cfg.roots)) as graph:
        now = deps.Now(cfg, graph)
        selected = set(model.rules) if everything else set(deps.affected(data, model, now))
        flows = {identifier for identifier in [*model.flows, *model.states, *model.structures, *model.anchor_distincts]
                 if everything or not deps.reusable(data, identifier, now)}
        selected.update(identifier for identifier, rule in model.rules.items() if not {
            model.file_of[identifier] + '::' + name for name in model.items_of(rule)
        } <= data['results'].get(identifier, {}).get('items', {}).keys())
        records = deps.test_dependencies(cfg, graph, now)
        test_scope = deps.test_scope(cfg)
        def ordinary_file(file):
            path = (cfg.root / file).resolve()
            return test_scope(file) and not path.is_relative_to(cfg.intent) and path != sentinel
        ordinary = set()
        for file, record in records.items():
            if not ordinary_file(file):
                continue
            readings = {nodeid: reading for nodeid, reading in data['tests'].items() if nodeid.partition('::')[0] == file}
            full = data['test_collection'].get(file, {})
            if (everything or '<unresolved>' in record or cache.test_signature(record) != data['test_deps'].get(file)
                    or not full or not full['tests'] or not set(full['tests']) <= readings.keys()
                    or any(reading['outcome'] != 'passed' for reading in readings.values())):
                ordinary.add(file)
        # An opaque test may change shared inputs for another test or rule.
        if any('<unresolved>' in record for file, record in records.items() if ordinary_file(file)):
            ordinary.update(file for file in records if ordinary_file(file))
            selected.update(model.rules)
            flows.update([*model.flows, *model.states, *model.structures, *model.anchor_distincts])
        if since:
            impact = graph.impact(since=since)
            ordinary.update(file for file in impact['tests'] if ordinary_file(file))
            files, dirty = set(impact['files']), set(impact['dirty'])
            selected.update(identifier for identifier, saved in data['deps'].items() if identifier in model.rules and any(
                key.startswith('node:') and key[5:] in dirty
                or key.startswith(('file:', 'module:')) and key.partition(':')[2] in files
                for key in saved.get('dependencies', {})))
        # A `fields` anchor's rule is checked on the calls its tests reach: rerun the tests that reached
        # it last time, every test while that is unknown.
        for identifier in selected:
            if any(getattr(home, 'anchor', None) and home.anchor.fields for home in model.rules[identifier].homes):
                reached = {test.partition('::')[0] for value in data['results'].get(identifier, {}).get('items', {}).values()
                           for test in value.get('tests', ())}
                ordinary.update(file for file in records if ordinary_file(file) and (file in reached or not reached))
        guards = history._guards({cfg.rel(path): path.read_text(encoding='utf-8-sig')
                                 for path in (cfg.root / 'tests').rglob('*.py')})
        rule_markers = {ast.dump(ast.Constant(identifier), include_attributes=False) for identifier in model.rules}
    return selected, flows, ordinary, records, guards, rule_markers


# flowguard: event CHECK_PYTEST(command: list, root: Path, output: Path, stream: bool)
def _run_check_pytest(command: list, root: Path, output: Path, stream: bool):
    """One top-level pytest Session, with the real output retained verbatim."""
    from contextlib import redirect_stdout, redirect_stderr
    from types import SimpleNamespace
    from .config import _INSERTED_PATHS
    from .plugin import _CURRENT
    import pytest
    if _CURRENT is not None and not _CURRENT.closed:
        raise MapError('check needs the top-level test session; it cannot start a nested pytest session')
    output.parent.mkdir(parents=True, exist_ok=True)
    captured = io.StringIO()
    previous_directory = Path.cwd()
    previous_paths, paths = sys.path, list(sys.path)
    owned = set(_INSERTED_PATHS)
    stdout, stderr = sys.stdout, sys.stderr
    class Output:
        def __init__(self, live, saved):
            self.live, self.saved = live, saved
            self.encoding = getattr(live, 'encoding', None) or 'utf-8'
        def write(self, text):
            captured.write(text)
            self.saved.write(text)
            if stream:
                self.live.write(text)
            return len(text)
        def flush(self):
            self.saved.flush()
            if stream:
                self.live.flush()
        def isatty(self):
            return False
    try:
        os.chdir(root)
        with output.open('w', encoding='utf-8', newline='') as saved:
            with redirect_stdout(Output(stdout, saved)), redirect_stderr(Output(stderr, saved)):
                status = int(pytest.main(command))
        return SimpleNamespace(returncode=status, stdout=captured.getvalue(), stderr='')
    finally:
        os.chdir(previous_directory)
        sys.path = previous_paths
        previous_paths[:] = paths
        _INSERTED_PATHS.clear()
        _INSERTED_PATHS.update(owned)


def _check(cfg, *, everything=False, since=None, deep=False, base=None, reports=None):
    import ast
    from . import deps, history
    from .loader import load
    stream_all = everything
    model = load(cfg)
    model.deep = deep
    def report(lines):
        if reports is None:
            print('\n'.join(lines))
        else:
            from .signals import constraint
            red = [constraint(line.removeprefix('red ')) for line in lines if line.startswith('red ')]
            grey = [line.removeprefix('grey ') for line in lines if line.startswith(('grey ', 'OPEN '))]
            reports.append(dict(source_changed=bool(red or grey), red=red, items=[dict(
                name='未覆盖', status='grey', complete=False, changes=[], reasons=grey)] if grey else []))
    historical = history.check(cfg, since)
    data = cache.read(cfg)
    retry_incomplete = bool((data.get('attempt') or {}).get('errors'))
    if not model.declared_items() and not everything and not retry_incomplete:
        # No intent item runs, so the ledger the plugin would report is compared here without pytest.
        from . import ledger as fallbacks
        result = _ledger_result(cfg)
        shown = [fallbacks.summary(result), *fallbacks.lines(result)] if result.red else []
        if shown and reports is None:
            print('\n'.join(shown))
        elif shown:
            reports.append(dict(source_changed=True, red=[], items=[],
                                ledger_red=[dict(text=finding.text, fix=list(finding.fix)) for finding in result.red]))
        if historical:
            report(['red ' + _action(message) for message in historical])
            return 1
        if shown:
            return 1
        print('FlowGuard check: no intent rules.')
        return 0
    sentinel = cfg.root / 'tests/test_flowguard_intent.py'
    if model.declared_items() and not sentinel.is_file():
        report(['red sentinel missing -> run python -m flowguard init'])
        return 1
    command = ['-vv' if stream_all else '-q', '-p', 'flowguard.intent.plugin', '--flowguard-record-tests']
    if deep:
        command.append('--flowguard-deep')
    if stream_all:
        command += ['-o', 'verbosity_test_cases=2', '--durations=10', '--flowguard-complete']
    if base is not None:
        command.append('--flowguard-base=' + base)
    initial_baseline = not data.get('collection') or retry_incomplete or deep and not data['collection'].get('deep', False)
    everything = everything or initial_baseline
    declared = set(model.declared_items())
    if stream_all:
        print('FlowGuard check --all: preparing source dependencies before pytest.', flush=True)
    selected, flows, ordinary, test_records, guards, rule_markers = _check_selection(
        cfg, model, data, everything, since, sentinel)
    extras = flows
    attempt = data.get('attempt') or {}
    failed_collection = (attempt.get('sentinel') is not None or attempt.get('collected')) and (
        attempt.get('missing') or attempt.get('sentinel') != 'ok')
    run = everything or selected or extras or ordinary or model.errors or failed_collection or not data.get('collection')
    executed = set()
    opaque_tests = {file for file in ordinary if file not in test_records or '<unresolved>' in test_records[file]}
    process_code = 0
    if run:
        output = cfg.cache / 'check-output.txt'
        if stream_all:
            scope = ': running full pytest'
            print(f'FlowGuard check --all{scope}; live output: {output}', flush=True)
        batch = list(command)
        if not everything:
            targets = {cfg.rel(cfg.intent), cfg.rel(sentinel), *ordinary}
            batch += ['--flowguard-rules=' + ','.join(sorted(selected | extras)), *sorted(targets)]
        started = time.time()
        process = _run_check_pytest(batch, cfg.root, output, stream_all)
        process_code = process.returncode
        output_parts = [process.stdout + process.stderr]
        data = cache.read(cfg)
        executed.update(selected)
        if not model.declared_items():
            lines = [f'FlowGuard check: full pytest exit {process_code}; details: {output}']
            lines.extend('red ' + _action(message) for message in historical)
            if process_code:
                actual = [line for part in output_parts for line in part.splitlines() if line.strip()]
                reasons = [line for line in actual if line.startswith('FlowGuard:')]
                lines.extend(reasons or actual[-5:])
            report(_limit(lines, cfg.check_lines))
            return process_code or int(bool(historical))
        if not data.get('attempt') or data['attempt'].get('stamp', 0) < started:
            report([f'red check did not finish -> read {output} and correct the reported error'])
            return process_code or 1
        if data['attempt'].get('sentinel') == 'ok' and not data['attempt'].get('missing'):
            for group in data['results'].values():
                group['items'] = {item: value for item, value in group['items'].items() if item in declared}
        if process_code == 0:
            completed = {file: record for file, record in test_records.items()
                         if (data['test_collection'].get(file, {}).get('stamp', 0) >= started
                             and data['test_collection'][file]['tests']
                             and all(data['tests'].get(nodeid, {}).get('outcome') == 'passed'
                                     for nodeid in data['test_collection'][file]['tests']))}
            with closing(build(cfg.root, roots=cfg.roots)) as graph:
                cache.save_test_dependencies(graph.con, completed)
                graph.con.commit()
    for (file, name), (markers, _) in guards.items():
        if rule_markers.intersection(markers):
            for nodeid, reading in data['tests'].items():
                if nodeid.partition('::')[0] == file and _test_name(nodeid) == name and reading['outcome'] == 'skipped':
                    historical.append(f'guard lost: {nodeid} was skipped -> restore the real marked test')
    probes = []
    revision = history._revision(cfg, since)
    if revision is not None and executed:
        old = cache.scan(cfg, history._texts(cfg, revision, cfg.rel(cfg.intent)))['rules']
        current = data['summary']['rules']
        # history.proven builds and reads the same map. Every proof is finished
        # before this function opens its write transaction, so it never waits on itself.
        proofs = {}
        for rid in sorted(executed):
            rule = model.rules[rid]
            parts = data['results'].get(rid, {}).get('items', {})
            if not parts or any(value.get('verdict') == 'red' for value in parts.values()):
                continue
            prior = [(row['fields'], row['expect']) for row in old.get(rid, {}).get('row_records', []) if not row['retired']]
            new_lines = {row['line'] for row in current[rid]['row_records']
                         if not row['retired'] and (row['fields'], row['expect']) not in prior}
            retained = {proof.get('signature') for value in parts.values() for proof in value.get('proven_rows', [])}
            for row in rule.live_rows:
                if row.line not in new_lines or history.current_row_signature(rule, row) in retained:
                    continue
                proof = history.proven(cfg, rule, row, revision)
                proofs.setdefault(rid, []).append(proof)
                probes.append(f'{rid} row L{row.line}: {proof["status"]}' + (': ' + proof['reason'] if proof.get('reason') else ''))
        with closing(build(cfg.root, roots=cfg.roots)) as graph:
            for rid, found in proofs.items():
                cache.save_proven(graph.con, model.rules[rid], found)
            graph.con.commit()
        data = cache.read(cfg)
    for group in data['results'].values():
        group['items'] = {item: value for item, value in group['items'].items() if item in declared}
    data['summary']['errors'].extend(error for error in model.errors if error not in data['summary']['errors'])
    data['history'], data['probes'] = historical, probes
    data['check_scope'] = ('deep probes and mutation-survival enabled; ' if deep else 'deep probes and mutation-survival not run (--deep); ') + f'{len(executed)} rules rerun, {len(model.rules) - len(executed)} reused; ' + (
        'all tests (previous run incomplete)' if retry_incomplete else 'all tests (initial baseline)' if initial_baseline
        else 'all tests (--all)' if everything else f'{len(test_records)} test files considered')
    if opaque_tests and not everything:
        data['check_scope'] += f'; {len(opaque_tests)} test files rerun for unresolved imports/data/children'
    owner_grey = _owner_rules_unverified(cfg, data) if stream_all else []
    report(render(cfg, data, check=True) + owner_grey)
    red = owner_grey or historical or data['summary']['errors'] or (data.get('attempt') or {}).get('errors') or any(
        value.get('verdict') == 'red' for rid, group in data['results'].items()
        if rid in data['summary']['rules'] and not data['summary']['rules'][rid].get('superseded_by') or rid is None
        for value in group.get('items', {}).values())
    current_test_scope = deps.test_scope(cfg)
    red = red or any(reading['outcome'] == 'failed' and current_test_scope(nodeid.partition('::')[0])
                    for nodeid, reading in data['tests'].items())
    return process_code or int(bool(red))


def _owner_rules_unverified(cfg, data):
    """check --all: a rule quoting the owner's words that stays grey fails, unless the ledger's
    [unverified] section lists it with a reason."""
    from . import ledger
    from .api import IntentError
    from .sources import parse
    listed = ledger.unverified(cfg)[0]
    lines = []
    for rid, item in data['summary']['rules'].items():
        result = data['results'].get(rid, {})
        # The --deep mutation probe (`live`) measures how tightly the tests bind a rule, not whether the rule
        # was checked: a `fields` anchor cannot be called directly by it, and its rule is still verified.
        checked = dict(result, items={key: value for key, value in result.get('items', {}).items()
                                      if value.get('kind') != 'live'})
        if item.get('superseded_by') or _rule_colour(item, checked) != 'grey' or rid in listed:
            continue
        try:
            source = parse(item.get('source', ''))
        except IntentError:
            continue        # The load check reports an unreadable source.
        if source.kind != 'owner':
            continue
        reasons = [message for value in result.get('items', {}).values() for message in value.get('grey', ())]
        lines.append(f'red {rid}: 规则有主人原话出处（{source.rids[0]}），现在是灰（未验证）：'
                     + (reasons[0] if reasons else 'no results yet')
                     + f' -> 恢复可观察；或在 {ledger.LEDGER} 的 [unverified] 段写一句理由：{rid} = '
                     + ledger._quote(ledger.PLACEHOLDER_UNVERIFIED))
    return lines


def _early_plugin(text):
    """Use pytest's project configuration so preparation precedes conftest imports."""
    if text.startswith('\ufeff'):
        return '\ufeff' + _early_plugin(text[1:])
    header = '[tool.pytest.ini_options]'
    data = tomllib.loads(text).get('tool', {}).get('pytest', {}).get('ini_options', {})
    options = data.get('addopts', '')
    if not isinstance(options, (str, list)):
        raise ValueError('pytest addopts must be text or a list of text options')
    parts = shlex.split(options) if isinstance(options, str) else list(options)
    plugin = 'flowguard.intent.plugin'
    if '-p' + plugin in parts or any(a == '-p' and b == plugin for a, b in zip(parts, parts[1:])):
        return text
    if any(not isinstance(part, str) for part in parts):
        raise ValueError('pytest addopts must be text or a list of text options')
    value = options.rstrip() + ' -p ' + plugin if isinstance(options, str) else [*options, '-p', plugin]
    line = 'addopts = ' + json.dumps(value.lstrip() if isinstance(value, str) else value, ensure_ascii=False) + '\n'
    section = re.search(r'^\[tool\.pytest\.ini_options\][ \t]*(?:#.*)?$', text, re.M)
    if not section:
        return text.rstrip() + '\n\n' + header + '\n' + line
    start = section.end()
    if start == len(text):
        text += '\n'
    start += 1
    next_section = re.search(r'^\[', text[start:], re.M)
    end = start + next_section.start() if next_section else len(text)
    body = text[start:end]
    setting = re.search(r'^[ \t]*addopts[ \t]*=', body, re.M)
    if setting:
        finish = body.find('\n', setting.end())
        while True:
            finish = len(body) if finish < 0 else finish + 1
            try:
                tomllib.loads(body[setting.start():finish])
                break
            except tomllib.TOMLDecodeError:
                if finish == len(body):
                    raise ValueError('cannot update pytest addopts without changing other settings')
                finish = body.find('\n', finish)
        body = body[:setting.start()] + line + body[finish:]
    else:
        body = body.rstrip() + '\n' + line + '\n'
    return text[:start] + body + text[end:]


NPM_HEADER = '// Generated by `python -m flowguard init`: FlowGuard\'s map checks inside `npm test`.'
NPM_CHECK = NPM_HEADER + '''
// It does one thing: run `python -m flowguard check --static` at the project root, print what it reports,
// and fail when anything is red (exit 1) or FlowGuard cannot run. Python is found in this order:
//   1. the FLOWGUARD_PYTHON environment variable, when set (then only that one);
//   2. the interpreter that ran `flowguard init`: RECORDED below;
//   3. `python3`, `python` and, on Windows, `py -3` on PATH.
// The first that can import flowguard runs the check; when none can, the test fails and lists what was tried.
@IMPORTS@
const ROOT = @ROOT@;
const RECORDED = @RECORDED@;

function interpreters() {
  if (process.env.FLOWGUARD_PYTHON) return [[process.env.FLOWGUARD_PYTHON]];
  const listed = [[RECORDED], ['python3'], ['python']];
  if (process.platform === 'win32') listed.push(['py', '-3']);
  return listed;
}

function findPython() {
  const tried = [];
  for (const [command, ...prefix] of interpreters()) {
    const probe = spawnSync(command, [...prefix, '-c', 'import flowguard'], { cwd: ROOT, encoding: 'utf8' });
    if (probe.status === 0) return { command, prefix, tried };
    const why = probe.error ? probe.error.message : ((probe.stderr || '').trim().split('\\n').pop() || 'exit ' + probe.status);
    tried.push([command, ...prefix].join(' ') + ': ' + why);
  }
  return { command: null, prefix: [], tried };
}

test('FlowGuard check --static', () => {
  const python = findPython();
  if (python.command === null) {
    throw new Error('FlowGuard: no Python that can import flowguard was found; set FLOWGUARD_PYTHON to the interpreter '
      + 'FlowGuard is installed in. Tried:\\n' + python.tried.join('\\n'));
  }
  const run = spawnSync(python.command, [...python.prefix, '-m', 'flowguard', 'check', '--static'], {
    cwd: ROOT, encoding: 'utf8', maxBuffer: 64 * 1024 * 1024, env: { ...process.env, PYTHONIOENCODING: 'utf-8' },
  });
  const output = ((run.stdout || '') + (run.stderr || '')).trimEnd();
  if (output) console.log(output);
  if (run.error) throw run.error;
  if (run.status !== 0) {
    throw new Error('FlowGuard check --static exit ' + run.status + (output ? ':\\n' + output : ''));
  }
}, 600000);
'''


def _packages(root):
    """The package.json files `init` serves: the project root's, else those up to two folders down."""
    if (root / 'package.json').is_file():
        return [root / 'package.json']
    return sorted(path for pattern in ('*/package.json', '*/*/package.json') for path in root.glob(pattern)
                  if not any(part == 'node_modules' or part.startswith('.') for part in path.relative_to(root).parts[:-1]))


def _npm_check(cfg, package):
    """Write the vitest (or, for a jest project, jest) test that runs `check --static`; returns what it did."""
    data = json.loads(package.read_text(encoding='utf-8-sig'))
    if not isinstance(data, dict):
        raise ValueError(f'{package}: package.json is not a JSON object')
    named = {**(data.get('dependencies') or {}), **(data.get('devDependencies') or {})}
    script = str((data.get('scripts') or {}).get('test', ''))
    runner = 'jest' if ('jest' in named or 'jest' in script) and 'vitest' not in named and 'vitest' not in script else 'vitest'
    module = runner == 'vitest' or data.get('type') == 'module'
    target = package.parent / ('flowguard.static.test.mjs' if runner == 'vitest' else 'flowguard.static.test.js')
    relative = os.path.relpath(cfg.root, package.parent).replace(os.sep, '/')
    if module:
        imports = ("import { test } from 'vitest';\n" if runner == 'vitest' else '') + \
            "import { spawnSync } from 'node:child_process';\nimport path from 'node:path';\nimport { fileURLToPath } from 'node:url';"
        root = f"path.resolve(path.dirname(fileURLToPath(import.meta.url)), {json.dumps(relative)})"
    else:
        imports = "const { spawnSync } = require('node:child_process');\nconst path = require('node:path');"
        root = f'path.resolve(__dirname, {json.dumps(relative)})'
    text = (NPM_CHECK.replace('@IMPORTS@', imports).replace('@ROOT@', root)
            .replace('@RECORDED@', json.dumps(sys.executable)))
    if target.exists() and not target.read_text(encoding='utf-8').startswith(NPM_HEADER):
        raise ValueError(f'{target}: an existing file has this name; rename it, then run init again')
    target.write_text(text, encoding='utf-8', newline='\n')
    static = f'Generated {cfg.rel(target)} ({runner}): npm test runs python -m flowguard check --static and fails on red.'
    if runner == 'jest':
        return static + '\nThe execution side supports vitest only: this jest project runs check --static alone.'
    from .vitest import wire
    return static + '\n' + wire(cfg, package)


def init(cfg):
    pyproject = cfg.root / 'pyproject.toml'
    text = pyproject.read_text(encoding='utf-8') if pyproject.is_file() else ''
    if '[tool.flowguard]' not in text:
        text = text.rstrip() + '\n\n[tool.flowguard]\n'
    pyproject.write_text(_early_plugin(text), encoding='utf-8')
    cfg.intent.mkdir(parents=True, exist_ok=True)
    sentinel = cfg.root / 'tests/test_flowguard_intent.py'
    if sentinel.exists() and sentinel.read_text(encoding='utf-8') != SENTINEL:
        raise ValueError(f'{sentinel}: an existing test needs merging with the intent sentinel')
    sentinel.parent.mkdir(parents=True, exist_ok=True)
    sentinel.write_text(SENTINEL, encoding='utf-8')
    conftest = sentinel.parent / 'conftest.py'
    content = conftest.read_text(encoding='utf-8') if conftest.exists() else ''
    if 'flowguard.intent.plugin' not in content:
        if 'pytest_plugins' in content:
            extra = 'pytest_plugins = ([pytest_plugins] if isinstance(pytest_plugins, str) else list(pytest_plugins)) + ["flowguard.intent.plugin"]\n'
        else:
            extra = 'pytest_plugins = ["flowguard.intent.plugin"]\n'
        conftest.write_text(content.rstrip() + '\n\n' + extra, encoding='utf-8')
    fragment = cfg.root / '.flowguard/ci.yml'
    fragment.parent.mkdir(parents=True, exist_ok=True)
    fragment.write_text('''# Merge these steps into the project CI after installing FlowGuard.
- uses: actions/checkout@v5
  with:
    fetch-depth: 0
- run: python -m flowguard check --all --deep
''', encoding='utf-8')
    agents = cfg.root / 'AGENTS.md'
    # Bytes outside the replaced block are kept, including their line endings.
    content = agents.read_bytes().decode('utf-8') if agents.exists() else ''
    newline = '\r\n' if '\r\n' in content else '\n'
    rules = PROJECT_RULES.replace('\n', newline)
    # The owner's repositories carry a level-one block whose commands 4.x no longer has.
    owner_block = re.compile(r'^# FlowGuard rules for the project agent[ \t]*\r?\n.*?(?=^#{1,6} |^<!-- flowguard:start -->|\Z)',
                             re.M | re.S)
    if '<!-- flowguard:start -->' in content:
        before, _, rest = content.partition('<!-- flowguard:start -->')
        _, _, after = rest.partition('<!-- flowguard:end -->')
        content = before + rules + (newline + after.lstrip('\r\n') if after.strip() else '')
        content = owner_block.sub('', content, count=1)
    elif re.search(r'^## FlowGuard rules for the project agent\s*$', content, re.M):
        content = re.sub(r'^## FlowGuard rules for the project agent\s*\n.*?(?=^## |\Z)', lambda _: rules + newline,
                         content, count=1, flags=re.M | re.S)
    elif owner_block.search(content):
        content = owner_block.sub(lambda match: rules + (newline if match.end() < len(content) else ''), content, count=1)
    else:
        content = content.rstrip() + newline + newline + rules
    agents.write_bytes(content.encode('utf-8'))
    print('Initialized intent sentinel, pytest plugin, CI fragment and four project rules.')
    for package in _packages(cfg.root):
        print(_npm_check(cfg, package))
    return 0


def _plugin_loaded(cfg, graph):
    """Whether pytest's own configuration (pyproject.toml or a mapped conftest.py) loads the FlowGuard plugin."""
    paths = [cfg.root / 'pyproject.toml'] + [cfg.root / node['file'] for node in graph.nodes(kind='module')
                                             if node['file'] and node['file'].rpartition('/')[2] == 'conftest.py']
    return any('flowguard.intent.plugin' in path.read_text(encoding='utf-8-sig') for path in paths if path.is_file())


def ledger(cfg, operation):
    """`ledger init` records the existing fallbacks as legacy; `ledger check` lists every difference."""
    from . import ledger as fallbacks
    if operation == 'init':
        with closing(build(cfg.root, roots=cfg.roots)) as graph:
            report = fallbacks.init(cfg, graph)
            loaded = _plugin_loaded(cfg, graph)
        if not loaded:
            report.append('pytest does not load the FlowGuard plugin yet, so ordinary tests cannot report the ledger: '
                          'run python -m flowguard init')
        print('\n'.join(report))
        return 0
    result = _ledger_result(cfg)
    if not result.present and not result.red:
        print(f'FlowGuard ledger: no {fallbacks.LEDGER}; python -m flowguard ledger init starts one from the current code.')
        return 0
    print('\n'.join([fallbacks.summary(result), *fallbacks.lines(result), *('未核对：' + line for line in result.grey)]))
    return int(bool(result.red))


def _ledger_result(cfg):
    """The ledger compared with the current map without running tests (only its deletion when there is none)."""
    from . import ledger as fallbacks
    baseline = cache.session_baseline(cfg)
    if not fallbacks.path(cfg).is_file():
        return fallbacks.absent(cfg, baseline)
    with closing(build(cfg.root, roots=cfg.roots)) as graph:
        return fallbacks.evaluate(cfg, graph, baseline=baseline)


def requests(cfg, options):
    if options.operation == 'add':
        raw = sys.stdin.buffer.read() if options.file == '-' else Path(options.file).read_bytes()
        item = store_request(cfg.root, raw, identifier=options.identifier, kind=options.kind,
                             supersedes=options.supersedes)
        print(f'stored {item["id"]} ({item["kind"]}, sha {item["sha256"][:12]}, {item["bytes"]} bytes)')
        from .differences import display
        display(f'这句话如果定下了一直成立的规矩，就写成 {cfg.rel(cfg.intent)}/ 里的规则，并以 {item["id"]} 为出处：'
                f'source="owner {item["id"]}: <原话里的那一句>"')
    elif options.operation == 'retire':
        retire_request(cfg.root, options.identifier, note=options.note)
        print(f'retired {options.identifier}: not the owner\'s words')
    else:
        items = owner_words(cfg.root)['rows']
        print(f'requests: {len(items)}; show ID for the stored words')
        for item in items:
            state = ('retired' if item.get('retired') else 'superseded' if item.get('superseded_by') else 'stored')
            if item.get('invalid') or item.get('edited'):
                state = item.get('invalid') or item.get('edited')
            print(f'  {item["id"]} {item["kind"] or "unverified"} {item["received"]} {state}')
    return 0


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    root = None
    if '--root' in argv:
        at = argv.index('--root')
        if at + 1 == len(argv):
            raise SystemExit('--root needs a project directory')
        root = argv[at + 1]
        del argv[at:at + 2]
    parser = argparse.ArgumentParser(prog='flowguard')
    parser.add_argument('--version', action='version', version=__version__)
    commands = parser.add_subparsers(dest='command')
    anchor_parser = commands.add_parser('anchor')
    anchor_operations = anchor_parser.add_subparsers(dest='operation', required=True)
    anchor_draft = anchor_operations.add_parser('draft')
    anchor_draft.add_argument('target')
    show_parser = commands.add_parser('show')
    show_parser.add_argument('query', nargs='?')
    show_parser.add_argument('--draft')
    show_parser.add_argument('--gaps')
    show_parser.add_argument('--full', action='store_true', help='Include decision sites and full candidate metadata')
    try_parser = commands.add_parser('try')
    try_parser.add_argument('anchor')
    try_parser.add_argument('inputs', nargs='*')
    try_parser.add_argument('--grid', action='store_true')
    watch_parser = commands.add_parser('watch')
    watch_parser.add_argument('arguments', nargs=argparse.REMAINDER)
    model_parser = commands.add_parser('model')
    model_operations = model_parser.add_subparsers(dest='operation', required=True)
    model_draft = model_operations.add_parser('draft')
    model_draft.add_argument('name')
    check_parser = commands.add_parser('check')
    check_parser.add_argument('--all', action='store_true')
    check_parser.add_argument('--deep', action='store_true', help='Run decision probes and mutation-survival checks')
    check_parser.add_argument('--since')
    check_parser.add_argument('--base', help='Compare behavior with this commit instead of the remembered session baseline')
    check_parser.add_argument('--static', action='store_true',
                              help='Map checks only, without pytest (any language FlowGuard reads, e.g. TS/JS, Prisma, SQL)')
    compare_parser = commands.add_parser('compare')
    compare_parser.add_argument('left')
    compare_parser.add_argument('right')
    commands.add_parser('init')
    ledger_parser = commands.add_parser('ledger', help='The fallback ledger: handlers that may end without raising')
    ledger_operations = ledger_parser.add_subparsers(dest='operation', required=True)
    ledger_operations.add_parser('init', help='Record every existing fallback as legacy')
    ledger_operations.add_parser('check', help='List every difference between the ledger and the code')
    req_parser = commands.add_parser('req')
    operations = req_parser.add_subparsers(dest='operation', required=True)
    add = operations.add_parser('add')
    add.add_argument('file')
    add.add_argument('--id', dest='identifier')
    add.add_argument('--kind', choices=('request', 'glossary', 'adoption'), default='request')
    add.add_argument('--supersedes', action='append', default=[])
    operations.add_parser('list')
    retire = operations.add_parser('retire')
    retire.add_argument('identifier')
    retire.add_argument('--not-owner', action='store_true', required=True)
    retire.add_argument('--note')
    options = parser.parse_args(argv)
    try:
        cfg = load_config(root or find_root())
        if options.command == 'anchor':
            return draft_anchor(cfg, options.target)
        if options.command == 'model':
            return draft_model(cfg, options.name)
        if options.command == 'try':
            return try_anchor(cfg, options.anchor, options.inputs, grid=options.grid)
        if options.command == 'watch':
            return watch(cfg, options.arguments)
        if options.command == 'compare':
            from .differences import compare, display, render as render_comparison
            result = compare(cfg.root, options.left, options.right)
            display(render_comparison(result))
            return int(result['status'] == 'red')
        if options.command == 'show':
            return show(cfg, options.query, draft=options.draft, gaps=options.gaps, full=options.full)
        if options.command == 'check' and options.static:
            if options.deep or options.since:
                raise ValueError('check --static runs no tests: --deep and --since need the pytest check')
            return static_check(cfg, everything=options.all, base=options.base)
        if options.command == 'check':
            return check(cfg, everything=options.all, since=options.since, deep=options.deep, base=options.base)
        if options.command == 'init':
            return init(cfg)
        if options.command == 'ledger':
            return ledger(cfg, options.operation)
        if options.command == 'req':
            return requests(cfg, options)
        return screen(cfg)
    except BrokenPipeError:
        raise               # The command entry exits quietly when the consumer closes stdout.
    except (ValueError, MapError, OSError) as error:
        print(f'flowguard: {error}', file=sys.stderr)
        return 2
