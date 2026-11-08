"""A short screen and one pytest check route over generated structure and intent."""
from __future__ import annotations

import argparse
import codecs
from contextlib import closing
import io
import json
import locale
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
import threading
import time
import tomllib

from flowguard import __version__
from flowguard.map.common import MapError
from flowguard.map.requests import owner_word, owner_words, retire_request, store_request
from flowguard.structure import build
from flowguard.structure.query import tokens
from . import cache
from .config import find_root, load_config


SENTINEL = '''"""Fail when declared FlowGuard intent was not collected."""
def test_flowguard_intent(request):
    from flowguard.intent.plugin import sentinel
    sentinel(request.config)
'''

PROJECT_RULES = '''<!-- flowguard:start -->
## FlowGuard rules for the project agent

1. At session start, look at `python -m flowguard` when the project has intent rules.
2. Before writing a decision, use `python -m flowguard show "what it decides"` to find its existing owner.
3. Write one rule, connect its source anchors, and add a literal regression row only when a decision has copies, the owner says everywhere, or a bug was fixed. Otherwise stay quiet.
4. After changing a bound decision run `python -m flowguard check`; CI runs `check --all`. Store actual owner words once with `req add`.
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


def screen(cfg):
    data = cache.read(cfg)
    if not data['summary']['rules']:
        print('\n'.join(render(cfg, data)))
        return int(bool(data['summary']['errors']))
    with closing(build(cfg.root, roots=cfg.roots)) as graph:
        from .deps import Now, stale
        now = Now(cfg, graph)
        for rid, result in data['results'].items():
            if rid not in data['summary']['rules']:
                continue
            saved = data['deps'].get(rid)
            if not saved or stale(saved, now):
                result['items'] = {'stale': dict(verdict='grey', red=[], grey=['cached result changed or unverified -> run check'], info=[])}
        print('\n'.join(render(cfg, data, graph=graph)))
    return int(bool(data['summary']['errors']))


def _candidate(candidate, full):
    if full:
        return json.dumps(candidate, ensure_ascii=False)
    return f'{candidate["id"]} {candidate.get("file", "")}:{candidate.get("line", "?")}: {candidate.get("reason", "source similarity only")}'


def _candidate_lines(found, full, prefix):
    candidates = found['candidates']
    visible = candidates if full else candidates[:5]
    result = [prefix + _candidate(candidate, full) for candidate in visible]
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
        found = graph.search_homes(target, sites=scope, not_same=excluded, words=words, k=None, weak=True)
        if not found['searched']:
            lines.append('copy search unavailable: ' + found.get('reason', 'no readable decision sites'))
        for candidate in found['candidates']:
            node = graph.node(candidate['id'])
            if node:
                candidate = dict(candidate, file=node['file'], line=node['line'])
            old = candidates.get(candidate['id'])
            if old is None or candidate.get('score', 0) > old.get('score', 0):
                candidates[candidate['id']] = candidate
    found = dict(candidates=sorted(candidates.values(), key=lambda row: (-row.get('score', 0), row['id'])))
    return list(dict.fromkeys(lines)) + _candidate_lines(found, full, 'unbound candidate ')


def _unmodelled(index, summary, *, root=None):
    references = {ref for item in summary['rules'].values() for ref in item.get('anchors', [])}
    references.update(value for relation in summary.get('distincts', []) for value in (relation['a'], relation['b']))
    sdk_root = Path(__file__).resolve().parents[2]
    internal = set()
    if root is not None and Path(root).resolve() == sdk_root:
        from .checkflow import covered_sdk_anchors
        internal = covered_sdk_anchors(root)
    def identity(anchor):
        return (anchor.name, anchor.target, anchor.file, anchor.source_digest,
                anchor.kind, anchor.target_line, anchor.parameters)
    used = {identity(a) for a in _anchor_targets(index, references)} | internal
    return sorted({a.name for a in index.entries if a.source_role == 'production' and identity(a) not in used})


def _observation_lines(cfg, graph, data, node):
    """Keep recorded source navigation equally honest for anchored functions."""
    tables = {r[0] for r in graph.con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    lines, observed = [], False
    if 'footprint' in tables:
        from .deps import Now, trace_changes
        now = Now(cfg, graph)
        for test, fingerprint, calls in graph.con.execute(
                'SELECT test,fp,call_lines FROM footprint WHERE node=?', (node['id'],)):
            observed = True
            saved = data['traces'].get(test)
            if fingerprint != node['fp'] or trace_changes(saved, now):
                lines.append(f'historical observation: {test}; source/test/known dependency changed or unverified -> run check --all')
            else:
                lines.append(f'inputs: last observed in {test} ' + (calls or '') + '; current code/test/known dependencies match')
                if saved.get('unknown'):
                    lines.append('runtime input boundary: dynamic data was not verified; this is a navigation clue, not a result proof')
    if not observed:
        lines.append('not observed in current test records -> run check --all for a complete recording')
    return lines


def _builtin_check_flow_lines(cfg, module, *, full=False):
    flow = module.CHECK_FLOW
    source = Path(module.__file__).resolve()
    line = next((number for number, text in enumerate(source.read_text(encoding='utf-8').splitlines(), 1)
                 if text.startswith('CHECK_FLOW =')), 1)
    lines = [f'FLOW {flow.id} (built-in check diagnostic model)', f'source: {source}:{line}',
             f'nodes ({len(flow.nodes)}):']
    for node in flow.nodes:
        detail = f'{node.name}: {node.reference} {node.phase}'
        if node.end:
            detail += ' [end]'
        if full:
            detail += f'; occurrence={node.occurrence}; caller={node.caller or "any"}'
        lines.append('  ' + detail)
    lines.append('edges: ' + ', '.join(f'{left}->{right}' for left, right in flow.edges))
    lines.append(f'relations ({len(flow.relations)}):')
    def reading(value):
        text = value.node + '.' + value.field
        if value.occurrence is not None:
            text += f'#{value.occurrence}'
        if value.view:
            text += ':' + value.view
        if type(value.equals) in (bool, int, float, str, bytes, type(None)):
            text += ' == ' + repr(value.equals)
        return text
    for relation in flow.relations:
        identifier = getattr(relation.rule, 'id', str(relation.rule))
        values = ', '.join(name + '<-' + reading(value) for name, value in relation.inputs.items())
        actual = ' actual<-' + reading(relation.actual) if relation.actual is not None else ''
        lines.append(f'  {identifier} on {relation.on or "matching event"}: {values}{actual}')
        if full:
            lines.append('    ' + getattr(relation.rule, 'decides', ''))
    if full:
        lines.append('model source: ' + flow.source)
    lines.extend([f'latest diagnostic log: {cfg.cache / "check-flow.jsonl"}',
                  'Historical logs do not verify the current run; this view executes no check.'])
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
    if query == 'CHECK_PIPELINE' and query not in rules and not draft:
        from . import checkflow
        print('\n'.join(_builtin_check_flow_lines(cfg, checkflow, full=full)))
        return 0
    with closing(build(cfg.root, roots=cfg.roots)) as graph:
        from .anchors import collect
        index = collect(graph)
        notice = _map_notice(graph)
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
            print('\n'.join(line for line in lines if line))
            return int(bool(data['summary']['errors']))
        if data['summary']['errors'] and any(query in (cfg.root / e['file']).read_text(encoding='utf-8-sig') for e in data['summary']['errors']):
            for error in data['summary']['errors']:
                print(f'red load {error["file"]}:{error["line"]}: {error["msg"]} -> fix the intent file')
            return 1
        anchors, pointers = _source_pointers(index, [query], graph, full=full)
        if anchors:
            print('ANCHOR ' + query)
            print('\n'.join(pointers))
            if draft:
                seen = set()
                for anchor in anchors:
                    node = graph.node(graph.canonical(anchor.target) or anchor.target)
                    if node and node['id'] not in seen:
                        seen.add(node['id'])
                        print('\n'.join(_observation_lines(cfg, graph, data, node)))
            unused = set(_unmodelled(index, data['summary'], root=cfg.root)) & {a.name for a in anchors}
            if unused:print('info: not referenced by a current model: ' + ', '.join(sorted(unused)))
            print('\n'.join(_copy_pointers(graph, index, anchors, [], data['summary'], [], query, full)))
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
                found = graph.search_homes(query, k=None, weak=True)
                if not found['searched']:
                    print('not searched: ' + found.get('reason', '') + ' -> bind the real decision site')
                print('\n'.join(_candidate_lines(found, full, 'candidate ')))
            return 0
        words = tokens(query)
        ranked = []
        for rid, rule in rules.items():
            score = 1000 if query.casefold() in {rid.casefold(), rule['decides'].casefold()} else 0
            score += 4 * len(words & tokens(rule['decides'] + ' ' + rule.get('doc', '')))
            if score:
                ranked.append((score, f'rule {rid}: {rule["decides"]} {rule.get("doc", "")}'))
        owners = {**graph.functions(), **{node['id']: node for node in graph.nodes(kind='class')}}
        for ident, item in owners.items():
            sites = graph.sites(ident)
            names = {ident.casefold(), item['qual'].casefold(), item['qual'].rsplit('.', 1)[-1].casefold()}
            score = 1000 if query.casefold() in names else 0
            score += 2 * len(words & tokens(' '.join(s['field'] + ' ' + (s['identity'] or '') for s in sites)))
            score += len(words & tokens(ident + ' ' + item['doc']))
            if score:
                ranked.append((score, f'{ident} {item["file"]}:{item["line"]}'))
        for item in graph.search(query):
            for alias in item['matches'].get('aliases', []):
                ranked.append((1000, f'{alias} -> {item["id"]} {item["file"]}:{item["line"]}'))
        ranked.sort(key=lambda row: (-row[0], row[1]))
        print('\n'.join(_limit([f'show {query}'] + ([notice] if notice else [])
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


def anchor_checks(cfg, *, index=None, automatic=False):
    from . import differences
    index = differences._source_index(cfg.root) if index is None else index
    issues = list(index.issues) + [issue for anchor in index.entries for issue in anchor.issues]
    red = list(dict.fromkeys(issue.message for issue in issues if issue.level == 'red'))
    grey = list(dict.fromkeys(issue.message for issue in issues if issue.level == 'grey'))
    agreement = differences.agreements(cfg.root, index=index, automatic=automatic)
    lines = ['red anchor: ' + message for message in red] + ['grey anchor: ' + message for message in grey]
    if agreement.get('active'):
        lines.extend(('red ' if agreement['status'] == 'red' else 'grey ' if agreement['status'] == 'grey' else '') + line
                     for line in differences.render(agreement).splitlines())
    unused = _unmodelled(index, cache.scan(cfg), root=cfg.root)
    if unused:
        lines.append('info: anchors not referenced by a current model: ' + ', '.join(unused[:5])
                     + (f'; {len(unused)-5} more' if len(unused)>5 else ''))
    return index, lines, bool(red) or agreement['status'] == 'red'


def behavior_changes(cfg, *, automatic=False, index=None):
    from . import differences
    index = differences._source_index(cfg.root) if index is None else index
    if not any(anchor.kind == 'sensor' for anchor in index.entries):
        return []
    try:
        report = differences.changed(cfg.root, automatic=automatic)
    except (OSError, ValueError, SyntaxError, MapError) as error:
        return [f'grey behavior comparison unavailable: {error}']
    if not report.get('selected') and not report.get('reasons'):
        return []
    if automatic and not report.get('automatic_eligible'):
        return ['Behavior comparison is check-only: ' + '; '.join(report.get('reasons') or ['measured cost exceeded the automatic budget'])]
    return ['Behavior changes:', *differences.render(report).splitlines()]


def check(cfg, *, everything=False, since=None, diagnose=False, shard=None, shard_report=None):
    if shard is not None:
        from .plugin import parse_shard
        parse_shard(shard)
        if not everything or since is not None:
            raise ValueError('--shard requires --all and cannot be combined with --since')
    if shard_report is not None and shard is None:
        raise ValueError('--shard-report requires --shard')
    report = Path(shard_report) if shard_report is not None else None
    if report is not None and report.exists():
        raise ValueError('shard report already exists; choose a fresh output path')
    started = time.time()
    options = dict(shard=shard) if shard is not None else {}
    status = _check_with_diagnostics(cfg, everything=everything, since=since, diagnose=diagnose, **options)
    if report is not None:
        attempt = cache.read(cfg).get('attempt') or {}
        recorded = attempt.get('shard') or {}
        if (attempt.get('stamp', 0) < started or not recorded
                or (recorded.get('shard_index'), recorded.get('shard_count')) != parse_shard(shard)):
            print('red shard did not finish a current recorded attempt; no report written', file=sys.stderr)
            return status or 1
        process = subprocess.run(['git', '-C', str(cfg.root), 'rev-parse', 'HEAD'], capture_output=True, text=True)
        payload = dict(attempt['shard'], sentinel=attempt['sentinel'], exit=int(status),
                       pytest_exit=attempt['exit'], errors=attempt['errors'],
                       source_sha=process.stdout.strip() if process.returncode == 0 else None,
                       interpreter=dict(version=list(sys.version_info[:3]), executable=sys.executable,
                                        prefix=sys.prefix, base_prefix=sys.base_prefix))
        report.parent.mkdir(parents=True, exist_ok=True)
        with report.open('x', encoding='utf-8') as target:
            json.dump(payload, target, ensure_ascii=False, sort_keys=True)
            target.write('\n')
    return status


def _check_with_diagnostics(cfg, *, everything=False, since=None, diagnose=False, shard=None):
    options = dict(shard=shard) if shard is not None else {}
    if not diagnose:
        return _checked(cfg, everything=everything, since=since, **options)
    from .checkflow import CheckObservation
    from .diagnostics import EventLog, report_diagnostic
    with CheckObservation(cfg) as observation:
        status = observation.call(_checked, cfg, everything=everything, since=since, **options)
    result = status or int(bool(observation.result['red']))
    messages = ['red check flow: ' + message for message in observation.result['red']]
    messages.extend('grey check flow: ' + message for message in observation.issues)
    if observation.result['grey'] and (everything or any(e.anchor == 'CHECK_SELECTION' for e in observation.events)):
        unseen = sum(reason.startswith('unobserved edge ') for reason in observation.result['grey'])
        messages.append(f'Check flow: coverage grey; {unseen} unobserved edges; stages: {observation.path}')
    for message in messages:
        error = report_diagnostic(message)
        if error is not None:
            issue = f'diagnostics unavailable: stdout reporting raised {type(error).__name__}'
            observation.issues.append(issue)
            with EventLog(observation.path, append=True) as writer:
                writer.write(dict(kind='diagnostic-unavailable', output='stdout', error=type(error).__name__))
            break
    return result


# flowguard: event CHECK_RUN(cfg: Config, everything: bool, since: str | None, shard: str | None)
def _checked(cfg: Config, *, everything: bool = False, since: str | None = None, shard: str | None = None):
    from .checkflow import observe
    options = dict(shard=shard) if shard is not None else {}
    status = _check(cfg, everything=everything, since=since, **options)
    red = observe(_check_sources, cfg)
    return status or int(red)


# flowguard: event CHECK_SOURCES(cfg: Config)
def _check_sources(cfg: Config):
    from .differences import display
    index, lines, red = anchor_checks(cfg)
    lines.extend(behavior_changes(cfg, index=index))
    if lines:
        display('\n'.join(lines))
    return red


def _full_pytest(command, root, output):
    """Tee the existing pytest subprocess, including its unfinished node line."""
    output.parent.mkdir(parents=True, exist_ok=True)
    encoding = 'utf-8' if sys.flags.utf8_mode else locale.getencoding()
    decoder = io.IncrementalNewlineDecoder(codecs.getincrementaldecoder(encoding)(), translate=True)
    parts, errors, stopped = [], [], threading.Event()
    with output.open('w', encoding='utf-8') as saved:
        read_fd, write_fd = os.pipe()
        def forward():
            try:
                with os.fdopen(read_fd, 'rb') as source:
                    while True:
                        chunk = source.read1(8192)
                        if stopped.is_set():
                            return
                        try:
                            text = decoder.decode(chunk, final=not chunk)
                            parts.append(text)
                            saved.write(text)
                            saved.flush()
                        except Exception as error:
                            errors.append(error)
                            text = ''
                        if text and not errors:
                            try:
                                sys.stdout.write(text)
                                sys.stdout.flush()
                            except Exception as error:
                                errors.append(error)
                        if not chunk:
                            return
            except Exception as error:
                errors.append(error)
        reader = threading.Thread(target=forward, daemon=True)
        with os.fdopen(write_fd, 'wb') as destination:
            reader.start()
            try:
                process = subprocess.run(command, cwd=root, stdout=destination, stderr=subprocess.STDOUT, text=True)
            except BaseException:
                stopped.set()
                raise
            finally:
                destination.close()
                reader.join(timeout=1 if stopped.is_set() else None)
    if errors:
        raise errors[0]
    process.stdout, process.stderr = ''.join(parts), ''
    return process


# flowguard: event CHECK_SELECTION(cfg: Config, model: object, data: dict, everything: bool, since: str | None, sentinel: Path)
def _check_selection(cfg: Config, model: object, data: dict, everything: bool, since: str | None, sentinel: Path):
    import ast
    from . import deps, history
    with closing(build(cfg.root, roots=cfg.roots)) as graph:
        now = deps.Now(cfg, graph)
        selected = set(model.rules) if everything else set(deps.affected(data, model, now))
        flows = {identifier for identifier in model.flows
                 if everything or identifier not in data['results'] or identifier not in data['deps']
                 or deps.stale(data['deps'][identifier], now)}
        impact = graph.impact(since=since) if since or graph.stats.get('changed') else dict(files=[], dirty=[], tests=[])
        if since:
            dirty, files = set(impact['dirty']), set(impact['files'])
            selected.update(rid for rid, saved in data['deps'].items() if rid in model.rules and any(
                key.startswith('node:') and key[5:] in dirty
                or key.startswith(('file:', 'module:')) and key.partition(':')[2] in files
                for key in saved.get('dependencies', {})))
        selected.update(rid for rid, rule in model.rules.items() if not {
            model.file_of[rid] + '::' + name for name in model.items_of(rule)
        } <= data['results'].get(rid, {}).get('items', {}).keys())
        # Reuse the dependency owner's same-key and uses closure, including --since seeds.
        seeded = dict(data, results={rid: value for rid, value in data['results'].items() if rid not in selected})
        selected = set(deps.affected(seeded, model, now))
        ordinary = set()
        for identifier in flows:
            for result in data['results'].get(identifier, {}).get('items', {}).values():
                ordinary.update(test.partition('::')[0] for test in result.get('drivers', ()))
        current_test_scope = deps.test_scope(cfg)
        def ordinary_file(file):
            path = (cfg.root / file).resolve()
            return current_test_scope(file) and not path.is_relative_to(cfg.intent) and path != sentinel
        by_file, unrecorded = {}, set()
        for nodeid, reading in data['tests'].items():
            file = nodeid.partition('::')[0]
            by_file.setdefault(file, []).append(reading)
            if nodeid not in data['traces']:
                unrecorded.add(file)
        test_records = deps.test_dependencies(cfg, graph, now)
        ordinary.update(file for file, record in test_records.items()
                        if '<unresolved>' in record or cache.test_signature(record) != data['test_deps'].get(file))
        tables = {row[0] for row in graph.con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if 'footprint' in tables:
            for (test,) in graph.con.execute('SELECT DISTINCT test FROM footprint'):
                if test in data['tests'] and ordinary_file(test.partition('::')[0]) and deps.trace_changes(data['traces'].get(test), now):
                    ordinary.add(test.partition('::')[0])
        ordinary.update(file for file in impact['tests'] if ordinary_file(file))
        for file, readings in by_file.items():
            if ordinary_file(file) and (file not in test_records or file in unrecorded):
                ordinary.add(file)
        for file in test_records:
            if ordinary_file(file):
                readings = by_file.get(file, [])
                if not readings or any(reading['outcome'] == 'failed' for reading in readings):
                    ordinary.add(file)
        guards = history._guards({cfg.rel(path): path.read_text(encoding='utf-8-sig')
                                 for path in (cfg.root / 'tests').rglob('*.py')})
        rule_markers = {ast.dump(ast.Constant(rid), include_attributes=False) for rid in model.rules}
        for (file, name), (markers, _) in guards.items():
            if rule_markers.intersection(markers) and ordinary_file(file):
                readings = [value for nodeid, value in data['tests'].items()
                            if nodeid.partition('::')[0] == file and _test_name(nodeid) == name]
                if not readings or any(value['outcome'] != 'passed' for value in readings):
                    ordinary.add(file)
    return selected, flows, ordinary, test_records, guards, rule_markers


# flowguard: event CHECK_PYTEST(command: list, root: Path, output: Path, stream: bool)
def _run_check_pytest(command: list, root: Path, output: Path, stream: bool):
    return (_full_pytest(command, root, output) if stream else
            subprocess.run(command, cwd=root, capture_output=True, text=True))


def _check(cfg, *, everything=False, since=None, shard=None):
    import ast
    from . import deps, history
    from .loader import load
    from .checkflow import observe
    stream_all = everything
    model = observe(load, cfg)
    historical = history.check(cfg, since)
    data = cache.read(cfg)
    retry_incomplete = bool((data.get('attempt') or {}).get('errors'))
    if not model.declared_items() and not everything and not retry_incomplete:
        if historical:
            print('\n'.join('red ' + _action(message) for message in historical))
            return 1
        print('FlowGuard check: no intent rules.')
        return 0
    sentinel = cfg.root / 'tests/test_flowguard_intent.py'
    if model.declared_items() and not sentinel.is_file():
        print('red sentinel missing -> run python -m flowguard init')
        return 1
    command = [sys.executable, *(['-u'] if stream_all else []), '-c', 'import sys; sys.path.insert(0,sys.argv.pop(1)); import pytest; raise SystemExit(pytest.main(sys.argv[1:]))',
               str(Path(__file__).resolve().parents[2]), '-vv' if stream_all else '-q', '-p', 'flowguard.intent.plugin', '--flowguard-record-tests']
    if stream_all:
        command += ['-o', 'verbosity_test_cases=2', '--durations=10']
    if shard is not None:
        command.append('--flowguard-shard=' + shard)
    initial_baseline = not data.get('collection') or retry_incomplete
    everything = everything or initial_baseline
    declared = set(model.declared_items())
    selected, flows, ordinary, test_records, guards, rule_markers = observe(
        _check_selection, cfg, model, data, everything, since, sentinel)
    extras = set(model.states) | set(model.structures) | set(model.anchor_distincts) | flows
    attempt = data.get('attempt') or {}
    failed_collection = (attempt.get('sentinel') is not None or attempt.get('collected')) and (
        attempt.get('missing') or attempt.get('sentinel') != 'ok')
    run = everything or selected or extras or ordinary or model.errors or failed_collection or not data.get('collection')
    executed, cut = set(), set()
    opaque_tests = {file for file in ordinary if file not in test_records or '<unresolved>' in test_records[file]}
    process_code = 0
    if run:
        output = cfg.cache / 'check-output.txt'
        if stream_all:
            scope = f' --shard {shard}: running complete intent and one ordinary partition' if shard else ': running full pytest'
            print(f'FlowGuard check --all{scope}; live output: {output}', flush=True)
        original = data
        remaining = set(selected)
        staged = not everything and bool(data['collection']) and all(
            rid in data['results'] for rid in model.rules) and not model.errors
        output_parts, fresh_contracts, first_started = [], {}, time.time()
        from .checkflow import _CURRENT
        diagnosing = _CURRENT.get() is not None
        diagnostic_batches = 0
        while True:
            ready = {rid for rid in remaining if not set(model.rules[rid].uses) & remaining} if staged else remaining
            ready = ready or remaining
            batch = list(command)
            if not everything:
                targets = {cfg.rel(cfg.intent), cfg.rel(sentinel), *ordinary}
                batch += ['--flowguard-rules=' + ','.join(sorted(ready | extras)), *sorted(targets)]
            if diagnosing:
                batch.append('--flowguard-diagnose')
                if diagnostic_batches:
                    batch.append('--flowguard-diagnose-append')
            started = time.time()
            process = observe(_run_check_pytest, batch, cfg.root, output, stream_all)
            if diagnosing:
                diagnostic_batches += 1
            process_code = process_code or process.returncode
            output_parts.append(process.stdout + process.stderr)
            data = observe(cache.read, cfg)
            executed.update(ready)
            if not model.declared_items() and everything:
                break
            if not data.get('attempt') or data['attempt'].get('stamp', 0) < started:
                break
            remaining -= ready
            for rid in ready:
                for result in data['results'].get(rid, {}).get('items', {}).values():
                    if 'own_contract' in result:
                        fresh_contracts[rid] = result['own_contract']
            if not remaining:
                break
            with closing(build(cfg.root, roots=cfg.roots)) as graph:
                now = deps.Now(cfg, graph)
                keep = set(deps.contract_cut(original, model, now, fresh_contracts, remaining))
                for rid in remaining - keep:
                    saved = original['deps'][rid]
                    updated = dict(saved, dependencies={key: now(key) for key in saved['dependencies']})
                    cache.save_dependencies(graph.con, {rid: updated})
                graph.con.commit()
            cut.update(remaining - keep)
            remaining = keep
            if not remaining:
                break
            ordinary, extras = set(), set()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text('\n'.join(output_parts), encoding='utf-8')
        if not model.declared_items():
            lines = [f'FlowGuard check: full pytest exit {process_code}; details: {output}']
            lines.extend('red ' + _action(message) for message in historical)
            if process_code:
                actual = [line for part in output_parts for line in part.splitlines() if line.strip()]
                reasons = [line for line in actual if line.startswith('FlowGuard:')]
                lines.extend(reasons or actual[-5:])
            print('\n'.join(_limit(lines, cfg.check_lines)))
            return process_code or int(bool(historical))
        if not data.get('attempt') or data['attempt'].get('stamp', 0) < started:
            print(f'red check did not finish -> read {output} and correct the reported error')
            return process_code or 1
        if data['attempt'].get('sentinel') == 'ok' and not data['attempt'].get('missing'):
            for group in data['results'].values():
                group['items'] = {item: value for item, value in group['items'].items() if item in declared}
        if process_code == 0 and shard is None:
            completed = {file: record for file, record in test_records.items()
                         if any(nodeid.partition('::')[0] == file and reading['stamp'] >= first_started
                                for nodeid, reading in data['tests'].items())}
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
        with closing(build(cfg.root, roots=cfg.roots)) as graph:
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
                    cache.save_proven(graph.con, rule, [proof])
                    probes.append(f'{rid} row L{row.line}: {proof["status"]}' + (': ' + proof['reason'] if proof.get('reason') else ''))
            graph.con.commit()
        data = cache.read(cfg)
    for group in data['results'].values():
        group['items'] = {item: value for item, value in group['items'].items() if item in declared}
    data['summary']['errors'].extend(error for error in model.errors if error not in data['summary']['errors'])
    data['history'], data['probes'] = historical, probes
    data['check_scope'] = f'{len(executed)} rules rerun, {len(model.rules) - len(executed)} reused; ' + (
        'all tests (previous run incomplete)' if retry_incomplete else 'all tests (initial baseline)' if initial_baseline
        else 'all tests (--all)' if everything else f'{len(test_records)} test files considered')
    if shard is not None:
        data['check_scope'] = f'{len(executed)} rules rerun; shard {shard}: complete intent, partial ordinary tests'
    if cut:
        data['check_scope'] += f'; {len(cut)} unchanged upper contracts'
    if opaque_tests and not everything:
        data['check_scope'] += f'; {len(opaque_tests)} test files rerun for unresolved imports/data/children'
    print('\n'.join(render(cfg, data, check=True)))
    red = historical or data['summary']['errors'] or (data.get('attempt') or {}).get('errors') or any(
        value.get('verdict') == 'red' for rid, group in data['results'].items()
        if rid in data['summary']['rules'] and not data['summary']['rules'][rid].get('superseded_by') or rid is None
        for value in group.get('items', {}).values())
    current_test_scope = deps.test_scope(cfg)
    red = red or any(reading['outcome'] == 'failed' and current_test_scope(nodeid.partition('::')[0])
                    for nodeid, reading in data['tests'].items())
    return process_code or int(bool(red))


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
- run: python -m flowguard check --all
''', encoding='utf-8')
    agents = cfg.root / 'AGENTS.md'
    content = agents.read_text(encoding='utf-8') if agents.exists() else ''
    if '<!-- flowguard:start -->' in content:
        before, _, rest = content.partition('<!-- flowguard:start -->')
        _, _, after = rest.partition('<!-- flowguard:end -->')
        content = before + PROJECT_RULES + '\n' + after.lstrip('\n')
    elif re.search(r'^## FlowGuard rules for the project agent\s*$', content, re.M):
        content = re.sub(r'^## FlowGuard rules for the project agent\s*\n.*?(?=^## |\Z)', lambda _: PROJECT_RULES + '\n',
                         content, count=1, flags=re.M | re.S)
    else:
        content = content.rstrip() + '\n\n' + PROJECT_RULES
    agents.write_text(content, encoding='utf-8')
    print('Initialized intent sentinel, pytest plugin, CI fragment and four project rules.')
    return 0


def requests(cfg, options):
    if options.operation == 'add':
        raw = sys.stdin.buffer.read() if options.file == '-' else Path(options.file).read_bytes()
        item = store_request(cfg.root, raw, identifier=options.identifier, kind=options.kind,
                             supersedes=options.supersedes)
        print(f'stored {item["id"]} ({item["kind"]}, sha {item["sha256"][:12]}, {item["bytes"]} bytes)')
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
    check_parser = commands.add_parser('check')
    check_parser.add_argument('--all', action='store_true')
    check_parser.add_argument('--diagnose', action='store_true', help='Record timed check stages and activated source-anchor events')
    check_parser.add_argument('--since')
    check_parser.add_argument('--shard', help='Run complete intent and one partition of the full ordinary collection (k/n)')
    check_parser.add_argument('--shard-report', help='Write a fresh JSON receipt after all check stages finish')
    compare_parser = commands.add_parser('compare')
    compare_parser.add_argument('left')
    compare_parser.add_argument('right')
    commands.add_parser('init')
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
        if options.command == 'compare':
            from .differences import compare, display, render as render_comparison
            result = compare(cfg.root, options.left, options.right)
            display(render_comparison(result))
            return int(result['status'] == 'red')
        if options.command == 'show':
            return show(cfg, options.query, draft=options.draft, gaps=options.gaps, full=options.full)
        if options.command == 'check':
            extra = dict(shard=options.shard, shard_report=options.shard_report) if options.shard is not None or options.shard_report is not None else {}
            return check(cfg, everything=options.all, since=options.since, diagnose=options.diagnose, **extra)
        if options.command == 'init':
            return init(cfg)
        if options.command == 'req':
            return requests(cfg, options)
        return screen(cfg)
    except (ValueError, MapError, OSError) as error:
        print(f'flowguard: {error}', file=sys.stderr)
        return 2
