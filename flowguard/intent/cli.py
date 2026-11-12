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
import typing

from flowguard import __version__
from flowguard.map.common import MapError, git_files
from flowguard.map.requests import owner_word, owner_words, retire_request, store_request
from flowguard.structure import build
from flowguard.structure.query import may_share, tokens
from . import cache
from .config import INIT_MARK, RECORDED_PYTHON, find_root, load_config


SENTINEL = '''"""Fail when declared FlowGuard intent was not collected."""
def test_flowguard_intent(request):
    from flowguard.intent.plugin import sentinel
    sentinel(request.config)
'''

PROJECT_RULES = '''<!-- flowguard:start -->
## FlowGuard rules for the project agent
1. Start each task with `python -m flowguard new-task`; read its brief (owner rules, open items) before you change code.
2. Run the project's tests. FlowGuard prints last; its first line counts each kind. `python -m flowguard show NAME` explains any name.
3. `red` means your change broke a recorded agreement: fix the code. Never add `except=`, remove a flowguard comment or edit `.flowguard/known.toml` to clear it without the owner's yes.
4. `known` and `before` were there before your task: do what the line says after `->`. Tell the owner only when it says `ask owner`.
5. `changed` means a function returns something else for the input shown: if you meant it, say so in your report; if not, fix it. `impact` and `not compared` are not failures.
6. When you find two places that must agree, mark each with `flowguard: same NAME` in the same change; when you find a problem only the owner can decide, add it to `.flowguard/known.toml` with `act = "ask"`.
7. Store the owner's own words once with `python -m flowguard req add - --id R<n>`, never your own text, and keep `.flowguard/rules.toml` current, each rule's source quoting those words.
<!-- flowguard:end -->
'''


# The commands and the line `--help` gives each.
COMMANDS = {
    'show': 'Find agreements, writers, readers, copies and rules of a name or of "what it decides"',
    'check': 'Recheck the affected rules and tests with pytest; --static runs the map checks without tests',
    'init': 'Wire FlowGuard into this project: pytest plugin, sentinel, CI fragment, rules block, npm test files',
    'new-task': 'Start the next task: record HEAD as the task baseline, then print the brief',
    'ledger': 'The fallback ledger: handlers that may end without raising',
    'req': "Store, list or retire the owner's own words, byte for byte",
}

DEPRECATED_COMMANDS = {'anchor', 'try', 'watch', 'model', 'compare'}


def _spelled(word):
    """One word of a printed command: bare when every shell reads it as it is, else in double quotes, which
    cmd.exe, PowerShell and POSIX shells all read (README: `show "what it decides"`); single quotes are not
    quotes in cmd.exe."""
    return word if re.fullmatch(r'[\w.:/@=,+%-]+', word) else json.dumps(word, ensure_ascii=False)


def _limit(lines, budget, more='show RULE for the complete result'):
    """The first `budget` lines; the last says how many lines and red lines (a line that starts as one)
    are left out and the command `more` that prints them."""
    if len(lines) <= budget:
        return lines
    kept = lines[:max(0, budget - 1)]
    hidden = lines[len(kept):]
    reds = sum(line.startswith(('red ', 'red: ', '红：')) for line in hidden)
    return kept + [f'... {len(hidden)} more lines' + (f' ({reds} red)' if reds else '') + ': ' + more]


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


BRIEF_LINES = 8            # design 4.7: the one FlowGuard output an agent surely reads before it writes code
BRIEF_RULES = 4
BRIEF_KNOWN = 2
BRIEF_WIDTH = 200
# The findings whose red is judged against the task's baseline: after new-task they are before, unless a file of
# theirs is still dirty. Intent, test and input reds stay red under any baseline (D3, D4).
BASELINE_FAMILIES = frozenset({'pair', 'writer', 'values', 'same', 'changed-alone', 'source', 'ledger'})


def _brief_line(text, more=0):
    """A rule or known line of the brief: at most BRIEF_WIDTH characters, the last of its kind with the count of
    the entries `show rules` lists besides."""
    if not more:
        return text if len(text) <= BRIEF_WIDTH else text[:BRIEF_WIDTH - 3] + '...'
    tail = f'; +{more} more: python -m flowguard show rules'
    text = text.removesuffix('.')
    width = BRIEF_WIDTH - len(tail)
    return (text if len(text) <= width else text[:width - 3] + '...') + tail


def _known_brief(entry):
    if entry.act == 'ask':
        return (f'known.{entry.id}: asked on {entry.asked}; leave it until the owner answers: {entry.ask}' if entry.asked
                else f'known.{entry.id}: ask owner: {entry.ask}')
    return f'known.{entry.id}: ' + ('fix' if entry.act == 'fix' else 'leave it') + f': {entry.why}'


def _brief_reds(cfg, data):
    """The reds the last check left that no baseline moves: intent load errors (the static scan), a failed
    verification or collection, red intent results and failed tests of pytest's scope, one per message."""
    from .deps import test_scope
    summary, attempt = data['summary'], data['attempt'] or {}
    reds = [f'load {error["file"]}:{error["line"]}: {error["msg"]}' for error in summary['errors']]
    reds += ['verification: ' + message for message in attempt.get('errors', [])]
    for result in data['results'].values():
        for value in result['items'].values():
            if value.get('kind') == 'load':
                reds.extend('load: ' + message for message in value.get('red', []))
    for rid, item in summary['rules'].items():
        result = data['results'].get(rid, {})
        if _rule_colour(item, result) == 'red':        # a red colour has items
            messages = [message for value in result['items'].values() for message in value.get('red', [])]
            reds.extend(f'{rid}: {message}' for message in messages or ['reported red'])
    in_scope = test_scope(cfg)
    reds += ['test ' + test for test, reading in data['tests'].items()
             if reading['outcome'] == 'failed' and in_scope(test.partition('::')[0])]
    if attempt.get('missing') or (attempt.get('collected') and attempt.get('sentinel') != 'ok'):
        reds.append('collection incomplete')
    return list(dict.fromkeys(reds))


def _dirty(cfg):
    """The files of the working tree that differ from HEAD, untracked ones too."""
    from flowguard.map.common import git_run
    listed = git_run(cfg.root, 'diff', '--name-only', '-z', '--relative', 'HEAD', '--').stdout
    listed += git_run(cfg.root, 'ls-files', '--others', '--exclude-standard', '-z').stdout
    return {os.fsdecode(name) for name in listed.split(b'\0') if name}


def _recounted(cfg, line):
    """Is this red of the last run one the brief counts from where it is read now: an intent rule's or a test's
    (the intent cache, `_brief_reds`), or an input problem of an intent file or a catalog file (the static scan and
    `sources.catalog`)?"""
    from .signals import family_of
    from .sources import CATALOG_FILES
    family = family_of(line['name'])
    if family in ('rule', 'test'):
        return True
    intent = cfg.rel(cfg.intent)
    files = [place.rpartition(':')[0] for place in line['places']]
    return family in ('input', '') and bool(files) and all(
        file in CATALOG_FILES or file == intent or file.startswith(intent + '/') for file in files)


def _last_reds(cfg, baseline):
    """(now before, still red) of the last run's reds (`cache.read_last`), but those the brief counts where they are
    read now (`_recounted`). When that run compared with another commit than `baseline` (new-task has moved it
    since), a red of a baseline-judged family whose places' files are all clean against HEAD is before now (D26);
    one that names no place, one with a dirty file and every red of another family still count."""
    from .signals import family_of
    last = cache.read_last(cfg)
    if last is None:
        return 0, 0
    reds = [line for line in last['lines'] if line['kind'] == 'red' and not _recounted(cfg, line)]
    judged = [line for line in reds if family_of(line['name']) in BASELINE_FAMILIES]
    if not judged or baseline is None or last['baseline'] in (None, baseline):
        return 0, len(reds)
    dirty = _dirty(cfg)
    moved = sum(bool(line['places']) and not any(place.rpartition(':')[0] in dirty for place in line['places'])
                for line in judged)
    return moved, len(reds) - moved


def _brief(cfg, data, baseline, note='', *, structure=''):
    """The brief (design 4.7, at most BRIEF_LINES lines, no map, no project code): the baseline with its note; the
    first rules of .flowguard/rules.toml in file order; the open matters of .flowguard/known.toml an agent must act
    on (ask, not asked yet; fix; leave; ask, asked; never ignore); one count of the open structure problems; and what
    the last run left: the reds new-task's moved baseline turned into before, the reds that still stand, and invalid
    entries of the two files."""
    from .sources import catalog
    version = '.'.join(__version__.split('.')[:2])
    first = f'FlowGuard {version} brief, baseline {baseline[:12] if baseline else "none (no Git commit)"}'
    head = [first + ('; ' + note.removeprefix('baseline: ') if note else '')]
    found = catalog(cfg)
    order = {'ask': 0, 'fix': 1, 'leave': 2}
    waiting = sorted((entry for entry in found.known.values() if entry.act != 'ignore'),
                     key=lambda entry: 3 if entry.act == 'ask' and entry.asked else order[entry.act])
    before, still = _last_reds(cfg, baseline)
    still += len(_brief_reds(cfg, data))
    tail = [f'{before} red from the previous task are now before'] if before else []
    if still:
        tail.append(f'{still} still red: python -m flowguard show --last')
    if found.issues:
        tail.append(f'{len(found.issues)} invalid entries in .flowguard/rules.toml or known.toml: python -m flowguard show rules')
    fixed = [*([structure] if structure else []), *(['; '.join(tail)] if tail else [])]
    known = [_brief_line(_known_brief(entry), len(waiting) - BRIEF_KNOWN if index == BRIEF_KNOWN - 1 else 0)
             for index, entry in enumerate(waiting[:BRIEF_KNOWN])]
    slots = min(BRIEF_RULES, BRIEF_LINES - len(head) - len(fixed) - len(known))
    rules = list(found.rules.values())
    shown = [_brief_line(f'rule.{rule.id}: {rule.text}', len(rules) - slots if index == slots - 1 else 0)
             for index, rule in enumerate(rules[:slots])]
    return [*head, *shown, *known, *fixed]


def screen(cfg, *, new_task=False):
    """The brief. It keeps the task baseline while HEAD descends from it, and on a detached HEAD moves or records
    none; `new_task` (`new-task`) starts the next task at HEAD, a detached one too."""
    from .health import brief_line
    baseline, note = cache.remember_baseline(cfg, new_task=new_task)
    data = cache.read(cfg)
    from .differences import display
    structure = brief_line(cfg)         # one line from the last check; the brief builds no map
    display('\n'.join(_brief(cfg, data, baseline, note, structure=structure)))
    return int(bool(data['summary']['errors']))


def _candidate(candidate, full):
    if full:
        return json.dumps(candidate, ensure_ascii=False)
    return f'{candidate["id"]} {candidate.get("file", "")}:{candidate.get("line", "?")}: {candidate.get("reason", "source similarity only")}'


def _candidate_lines(found, full, prefix):
    candidates = found['candidates']
    visible = candidates if full else candidates[:3]
    result = [prefix + _candidate(candidate, full) + (' [lead]' if not full else '') for candidate in visible]
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
    return list(dict.fromkeys(lines)) + _candidate_lines(found, full, 'lead unbound candidate ')


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
        return '；'.join(shown) + (f'; plus {len(values) - len(shown)} classes: show --full {rid} lists all' if len(shown) < len(values) else '')
    lines = [f'undecided: rule {rid} has no result for {len(silent)} classes (total {key["cells"]} classes): {listed(silent)}']
    undecided = [cell for cell in gaps.get('cells', ()) if cell in silent]
    if undecided and gaps.get('total'):
        lines.append(f'red: {"、".join(gaps["total"])} declares total=True, but {len(undecided)} classes have no rule result: {listed(undecided)}'
                     f' -> give these cases a result in the rules, or remove total=True')
    elif undecided and len(undecided) < len(silent):
        lines.append(f'of these, {len(undecided)} classes also have no result from another rule: {listed(undecided)}')
    return lines


def show_last(cfg, full=False):
    """`show --last`: which run it was and when (`FlowGuard last run: pytest at 2026-11-12 14:03:51`, local time), the
    run's first line, then every one of its lines (no budget, no cut, full paths) with its detail indented under
    it; how many members an `act = "ignore"` entry of known.toml (or a `[structure]` decision) covered, when any
    did; the deprecated features the run used; the unchanged points an explicit comparison compared; and the
    5.0-deprecated heuristic leads, which no longer get a line, under `deprecated leads (5.0):`. Read from
    the cache (`cache.read_last`), without building the map."""
    from .differences import display
    last = cache.read_last(cfg)
    if last is None:
        print('FlowGuard: no last run recorded')
        return 0
    lines = [f'FlowGuard last run: {last["run"]} at {time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(last["stamp"]))}',
             last['title']]
    for line in last['lines']:
        lines.append(f'{line["kind"]}: {line["text"]}' + (f' -> {line["step"]}' if line['step'] else ''))
        lines.extend('    ' + detail for detail in line['detail'])
    if last['ignored']:
        lines.append(f'ignored: {last["ignored"]} (act = "ignore")')
    if last['deprecated']:
        lines.append('deprecated features used (5.0): ' + ', '.join(last['deprecated']))
    if last.get('compared'):
        lines.append('compared, unchanged:')
        lines.extend('    ' + text for text in last['compared'])
    leads = [lead for lead in last.get('hidden', ()) if lead['text'].strip()]
    if leads:
        lines.append('deprecated leads (5.0):')
        lines.extend('    ' + (f'{lead["feature"]}: ' if lead['feature'] else '') + lead['text'].strip() for lead in leads)
    display('\n'.join(lines))
    return 0


def _finding_state(last, entry):
    """What the last run (`cache.read_last`) said of a known entry's finding."""
    if last is None:
        return 'no run recorded'
    names = {(line['kind'], line['name']) for line in last['lines']}
    if ('known fixed?', f'known.{entry.id}') in names:
        return 'not found in the last run (known fixed?)'
    return 'found in the last run' if any(name == entry.finding for _, name in names) else 'not reported in the last run'


def show_catalog(cfg, query, full=False):
    """`show rules`: every rule of .flowguard/rules.toml (its text, its source and whether it holds now, the intent
    declarations that cite it), every entry of .flowguard/known.toml (act, why, ask, fix, its sites resolved on the
    map, its finding and what the last run said of it, its source), then the input problems of both files; `show
    rule.<id>` and `show known.<id>` one entry. Exit 1 when an input problem is listed (or the entry is missing)."""
    from .differences import display
    from .sources import KNOWN, RULES, catalog, catalog_authority, citing, known_sites, parse, shared_archive
    found = catalog(cfg)
    resolved, unresolved = [], []
    if found.known:                     # only a known entry's sites need the map
        with closing(build(cfg.root, roots=cfg.roots)) as graph:
            resolved, unresolved = known_sites(graph, found.known.values())
    sites = {entry.id: entry for entry in resolved}
    problems = [*found.issues, *unresolved]
    archive, cited, last = shared_archive(cfg.root), citing(cfg), cache.read_last(cfg)
    table, _, wanted = query.partition('.')
    rules = [rule for rule in found.rules.values() if query == 'rules' or table == 'rule' and rule.id == wanted]
    entries = [entry for entry in found.known.values() if query == 'rules' or table == 'known' and entry.id == wanted]
    if query != 'rules':     # the entry's own problem, and its file's (an entry of an invalid file is not read)
        problems = [issue for issue in problems if issue.subject in (query, RULES if table == 'rule' else KNOWN)]
    cited_words = [parse(item.source, strict=True) for item in [*rules, *entries] if item.source]
    archive.read([source.rids[0] for source in cited_words if source.kind == 'request'])     # one listing for all
    lines = [f'FlowGuard rules: {len(found.rules)} in {RULES}, {len(found.known)} known in {KNOWN}, '
             f'{len(problems)} input problems'] if query == 'rules' else []
    for rule in rules:
        valid, reason = catalog_authority(parse(rule.source, strict=True), cfg, archive)
        lines.append(f'rule.{rule.id}: {rule.text}')
        lines.append(f'    source: {rule.source} ' + ('(holds)' if valid else f'(does not hold: {reason})'))
        lines.extend(f'    cited by {place}' for place in cited.get(rule.id, ()))
    for entry in entries:
        act = (f'ask, asked on {entry.asked}' if entry.asked else 'ask, not asked yet') if entry.act == 'ask' else entry.act
        lines.append(f'known.{entry.id}: act {act}')
        lines.extend(f'    {key}: {getattr(entry, key)}' for key in ('why', 'ask', 'fix') if getattr(entry, key))
        for site in entry.sites:
            lines.append(f'    site {site}' + ('' if entry.id in sites else ' (see the input problem below)'))
        if entry.finding:
            lines.append(f'    finding {entry.finding}: {_finding_state(last, entry)}')
        if entry.source:
            valid, reason = catalog_authority(parse(entry.source, strict=True), cfg, archive)
            lines.append(f'    source: {entry.source} ' + ('(holds)' if valid else f'(does not hold: {reason})'))
    for issue in problems:
        _, (place,), what, step = issue.parts[0]
        lines.append(f'input {issue.name}: {place} {what} -> {step}')
    if query != 'rules' and not rules and not entries and not problems:
        lines.append(f'{query} is not in {RULES if table == "rule" else KNOWN}: python -m flowguard show rules lists every entry')
        display('\n'.join(lines))
        return 1
    display('\n'.join(lines))
    return int(bool(problems))


def show(cfg, query=None, *, draft=None, gaps=None, full=False, last=False):
    if last:
        if query or draft or gaps:
            raise ValueError('show --last takes no NAME: python -m flowguard show --last')
        return show_last(cfg, full)
    from .sources import catalog_files
    if query and not draft and not gaps and (query == 'rules' or query.startswith(('rule.', 'known.'))) and catalog_files(cfg):
        return show_catalog(cfg, query, full)      # without a catalog file these names are looked up as before
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
                ranked.append((2000 - bool(row['unclear']), f'writes {row["model"] or row["table"]}.{row["field"] or row["db_column"]} '
                               f'{where} {row["function"]} ({row["kind"]}{unclear})'))
            from . import health, owners as checks       # several files write it and nobody owns it: say so first
            change = checks.Change(cfg, graph, None)
            for issue in health.writers(change, index, written).issues:
                ranked.append((2001, f'structure: {issue.text} -> {issue.step} ' + ' '.join(issue.entry)))
            ranked.extend((2001, line) for line in health.co_written(change, query))
            ranked.extend((1999 - order, line) for order, line in enumerate(checks.field_lines(graph, query, written)))
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
        lines = [f'show {query}'] + ([notice] if notice else []) + [line for _, line in ranked]
        display('\n'.join(lines if full else _limit(lines, cfg.screen_lines,
                                                     f'python -m flowguard show {_spelled(query)} --full lists them all')))
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






class _Own:
    """What `check` finds itself, beside the deliveries of its pytest batch (`signals.delivery`): findings
    (`health.Issue`) of the families that need no map, lines already of their kind, the families and finding names
    its own checks judged in full (`ran`: a known entry naming one that is no longer found is `known fixed?`), and
    its batch's pytest exit code, seconds (FlowGuard's own share of them is in the batch's report), output file and
    the end of that output."""

    def __init__(self):
        self.issues, self.lines, self.code, self.seconds, self.output, self.tail = [], [], 0, 0.0, None, []
        self.ran = set()        # what check's own checks judged in full (`signals.deliver`'s `ran`)
        self.touched = set()    # the members of its own findings this change touches (`signals.deliver`)

    def red(self, family, name, subject, what, step, *, places=(), files=(), detail=()):
        from .signals import finding
        self.issues.append(finding(family, name, subject, [what], step, places=places, files=[file for file in files if file],
                                   detail=detail))

    def history(self, messages):
        """The reds of the intent rules' history (`history.check`): a rule, row or guard removed without its reason."""
        for message in messages:
            what, step = _step_of(message, 'show the rule and correct its source, binding or regression rows')
            subject, colon, rest = what.partition(': ')
            self.red('input', f'history:{what}', subject if colon else 'history', rest if colon else what, step)

    def delivery(self):
        from .signals import delivery
        return delivery(self.issues, self.lines, touched_functions=self.touched, ran=self.ran)


def _step_of(message, step):
    """(what, step) of a message that may carry its own step after ' -> ', in ASCII; else `step`."""
    from .signals import ascii_text
    what, arrow, own = ascii_text(message).partition(' -> ')
    return what, own if arrow else step


def _index_findings(index):
    """The findings of the flowguard comments, in the words of a pytest session: a malformed comment is red (it
    disables checks, D4), and a source file that does not parse is not compared, only that file."""
    from .signals import ascii_text, finding, not_compared
    reds, unparsed = {}, {}
    for issue in index.issues:
        place = f'{issue.file}:{issue.line}' if issue.line else issue.file
        if issue.level == 'red':
            what, _, step = ascii_text(issue.message).partition(' -> ')
            entry = reds.setdefault(f'comment:{place}:{issue.code}', dict(place=place, file=issue.file, whats=[],
                                                                          step=step or 'correct this flowguard comment'))
            entry['whats'].append(what)
        elif issue.code == 'source-syntax':
            unparsed.setdefault(issue.file, []).append('cannot be parsed: ' + ascii_text(issue.message))
    return ([finding('input', name, f'comment {entry["place"]}', entry['whats'], entry['step'], places=(entry['place'],),
                     files=(entry['file'],)) for name, entry in reds.items()],
            [not_compared(file, reasons, places=(file,)) for file, reasons in unparsed.items()])


def _ledger_findings(result):
    """The fallback ledger's findings, in the words of a pytest session, as (issues, lines, ran): each red one line,
    the entry to copy in its detail (`ledger check` prints it as well); the entries of a later FlowGuard, which check
    nothing here, not compared; and the ledger family in `ran` when a ledger was compared with the map in full, none
    of it unverified, as a pytest session names it (a known entry naming a ledger finding no longer found is then
    `known fixed?`)."""
    from .ledger import LEDGER
    from .signals import LEDGER_STEP, ascii_text, finding, not_compared
    issues = [finding('ledger', f'ledger:{red.text}', 'ledger', [ascii_text(red.text)], LEDGER_STEP,
                      places=(LEDGER, *re.findall(r'(?<![\w./-])[\w./-]+\.[A-Za-z]\w*:\d+', red.text)), files=(LEDGER,),
                      detail=list(red.fix)) for red in result.red]
    lines = [not_compared(LEDGER, [ascii_text(reason) for reason in result.later], places=(LEDGER,))] if result.later else []
    return issues, lines, {'ledger'} if result.present and not result.grey else set()


def _legacy_lines(listed):
    """`--all`: a before line for each kind of handler body of the ledger's unreviewed legacy handlers that do not
    hand their error on (`ledger.open_legacy`, its heading and next step in each line's detail)."""
    from .ledger import LEDGER
    from .signals import BEFORE_STEP, Line, ascii_text
    if not listed:
        return []
    heading, *groups, step = (ascii_text(line).strip() for line in listed)
    return [Line('before', 'ledger:legacy:' + group.partition(':')[0], '', 'ledger legacy: ' + group.replace(' handlers:', ' handlers: ', 1),
                 BEFORE_STEP, (LEDGER,), (heading, step)) for group in groups]


def _declared_at(model, identifier):
    """`file:line` of the declaration `identifier` (as a pytest session names it), '' when the model has none."""
    declaration = (model.rules.get(identifier) or model.states.get(identifier) or model.structures.get(identifier)
                   or model.flows.get(identifier) or model.anchor_distincts.get(identifier))
    return f'{model.file_of[identifier]}:{declaration.line}' if declaration is not None and identifier in model.file_of else ''


def _site(rule, target):
    """The place of a rule home's function as the 4.3 lines spell one, `path:qualified name`; its target without an
    anchor."""
    home = next((home for home in rule.homes if home.target == target and getattr(home, 'anchor', None)), None)
    return f'{home.anchor.file}:{home.anchor.qual}' if home is not None else target


def _rule_finding(model, rid, values):
    """The one `rule:ID` finding of an intent rule's red results, in the words a pytest session gives the same results
    (`plugin.Observations._rule_red`): the rule's own reds first, then the code's at its homes (the smallest input
    first), its first step from `signals.rule_steps` over every red, every step and the owner's words in its detail."""
    from .signals import finding, rule_steps
    from .sources import parse
    rule = model.rules[rid]
    where = _declared_at(model, rid)
    sites = [_site(rule, home.target) for home in rule.homes if not hasattr(home, 'scenario')]
    whats, said, at, places = [], [], [], []
    for value in values:
        place = _site(rule, value['target']) if value.get('target') else None
        for message in value['red'] or ['reported red']:
            what = said_text = str(message)
            counted = re.match(r'(?:\S+: )?(\d+ of \d+ (?:cells|rows) disagree); smallest (.+? -> rule .+?)(?: \((row L\d+)\))?$', what)
            if counted and place:       # the engine's count of one home: its smallest input first, as the code's red reads
                what = f'{counted[2]} at {place} ({counted[1]}' + (f', {counted[3]})' if counted[3] else ')')
            whats.append(what)
            said.append(said_text)
            places.extend(item for item in (where, place, *sites) if item)
            if place and place not in at:
                at.append(place)
    whats.sort(key=lambda text: not text.startswith(('self: ', 'row ', 'conflict ', 'gap in ')))
    steps = [step.rstrip('; ') for step in rule_steps(rid, at or sites or [rid + ' binding'], where, said)]
    source = parse(rule.source)
    return finding('rule', f'rule:{rid}', f'rule {rid}', whats, steps[0] if steps else '', places=tuple(dict.fromkeys(places)),
                   files=[model.file_of[rid]] if rid in model.file_of else [],
                   detail=[*steps, f'{rid} source: {source.quote or source.text}'])


def _cache_findings(cfg, model, data):
    """check's own findings from the intent results it ran or reused (`cache.read`), in the words of a pytest
    session, as (issues, lines): intent load errors, an unfinished verification or collection and a removed rule,
    row or guard (red, D3, D4); each red intent rule (`_rule_finding`) or other declaration; a cited source that
    already failed at the baseline (before); a failed test of pytest's scope (red); and each grey intent item, or a
    rule without results, not compared."""
    from .deps import test_scope
    from .health import LINES_ONLY, Issue
    from .plugin import FLOW_STEP
    from .signals import BEFORE_STEP, ascii_text, finding, not_compared
    own = _Own()
    summary, attempt = data['summary'], data.get('attempt') or {}
    for error in summary['errors']:
        place = f'{error["file"]}:{error["line"]}'
        own.red('input', f'load:{place}', f'load {place}', ascii_text(error['msg']),
                'correct this declaration; until then none of its file is checked', places=(place,), files=(error['file'],))
    order = {item: number for number, item in enumerate(model.declared_items())}
    def values(rid):
        items = data['results'].get(rid, {}).get('items', {})
        return [dict(value, item=item) for item, value in sorted(items.items(), key=lambda pair: order.get(pair[0], len(order)))]
    for value in values(None):              # an intent file that does not load: its `load` item
        for message in value.get('red') or ['reported red']:
            found = re.match(r'(.+?):(\d+): (.*)', str(message), re.S)
            place = f'{found[1]}:{found[2]}' if found else value['item'].partition('::')[0]
            own.red('input', f'load:{place}', f'load {place}', ascii_text(found[3] if found else message),
                    'correct this declaration; until then none of its file is checked', places=(place,),
                    files=(place.partition(':')[0],))
    collected = attempt and (attempt.get('sentinel') is not None or attempt.get('collected') or attempt.get('selected')
                             or attempt.get('deferred'))
    if collected and (attempt.get('missing') or attempt.get('sentinel') != 'ok'):
        own.red('input', 'collection:intent', 'collection', 'a declared intent item or the sentinel was not collected',
                'run python -m flowguard init and collect the complete intent path')
    for message in attempt.get('errors', []):
        own.red('input', f'verification:{message}', 'verification', *_step_of(message, 'correct the reported error and run check'))
    own.history(data.get('history', []))
    kinds = {'flow': 'flow', 'states': 'states', 'structure': 'structure', 'anchor_distinct': 'distinct'}
    for rid, item in summary['rules'].items():
        if item.get('superseded_by'):
            continue
        results = values(rid)
        if not results:
            own.lines.append(not_compared(rid, ['no results yet']))
        reds = [value for value in results if value.get('red') or value.get('verdict') == 'red']
        if reds and rid in model.rules:
            own.issues.append(_rule_finding(model, rid, reds))
        others = {}
        for value in [] if rid in model.rules else reds:
            kind = kinds.get(value.get('kind'), 'rule')
            where = _declared_at(model, rid)
            entry = others.setdefault((kind, value.get('target') or ''), dict(whats=[], where=where, step=FLOW_STEP.format(id=rid)
                                      if kind == 'flow' else f'correct the code or {kind} {rid} at {where}'))
            entry['whats'] += [ascii_text(message) for message in value.get('red') or ['reported red']]
        for (kind, target), entry in others.items():
            own.issues.append(finding('flow' if kind == 'flow' else 'rule', f'{kind}:{rid}', f'{kind} {rid}', entry['whats'],
                                      entry['step'], function=target, places=(entry['where'],) if entry['where'] else ()))
        for value in results:
            if value.get('before'):         # a cited source that already failed at the baseline (`engine._judged`)
                where = _declared_at(model, rid) or value['item'].partition('::')[0]
                reasons = tuple(dict.fromkeys(ascii_text(reason) for reason in value['before']))
                subject = f'source {rid}'
                own.issues.append(Issue(f'source:{rid}', LINES_ONLY, subject, f'{subject}: {reasons[0]}', BEFORE_STEP,
                                        files=frozenset({where.partition(':')[0]}), family='source', subject=subject,
                                        parts=(('', where, reasons[0], BEFORE_STEP),), detail=reasons))
            if value.get('verdict') == 'grey':
                own.lines.append(not_compared(value['item'].partition('::')[2], [str(reason) for reason in value.get('grey', ())]
                                              or ['unverified']))
    in_scope = test_scope(cfg)
    for test, value in data.get('tests', {}).items():
        file = test.partition('::')[0]
        if value.get('outcome') == 'failed' and in_scope(file):
            reason = value.get('reason') or value.get('phase')
            own.red('test', f'test:{test}', f'test {test}', f'{reason} (outside the project)' if value.get('kind') == 'env' else reason,
                    'rerun this test after correcting the cause', places=(file,), files=(file,))
    return own.issues, own.lines


def _judged_names(model, data):
    """The finding names of the declarations every intent result of which check ran or reused judged (none
    unverified), as a pytest session names them (`plugin.Observations._judged_names`): `rule:ID` (`flow:ID`, ...),
    and `source:ID` when every result passed, which none does whose source fails. A known entry naming one of them
    that is no longer found is `known fixed?`."""
    from .plugin import ITEM_KINDS
    judged = set()
    for rid, group in data['results'].items():
        results = list(group.get('items', {}).values())
        if rid is None or not results or any(value.get('verdict') == 'grey' for value in results):
            continue
        judged.add(f'rule:{rid}' if rid in model.rules else f'{ITEM_KINDS.get(results[0].get("kind"), "rule")}:{rid}')
        if all(value.get('verdict') == 'ok' for value in results):
            judged.add(f'source:{rid}')
    return judged


def _same_name_findings(cfg, index, compared, touched, baseline):
    """D24 and design 4.5: the same-name copies check's pytest batch did not compare (`compared`: the names it did).
    Where their current code differs (`differences._compare_pairs`), the copies are compared as a pytest session
    compares them (`plugin.compare_copies`): sealed, now and at `baseline`, on the inputs where they differ. A pair
    that differs where it agreed at the baseline (or a copy the baseline lacks; without a baseline every copy) is red,
    one that already differed there is old: `before` or `known` where this change touches a copy's file (the member
    is touched then, as in a pytest session), else no line. Copies of another signature are red where they are this
    change's, and what could not be compared is not compared. (issues, lines, ran, touched functions): `ran` names
    the groups whose every pair was compared and agreed (`same:NAME`), whose known entry is then `known fixed?`."""
    import math
    from ..map.common import git_renames, read_source
    from .differences import _compare_pairs
    from .plugin import _module_at, compare_copies
    from .runtime import Runtime, sealed
    from .signals import finding, not_compared
    issues, lines, ran, members = [], [], set(), set()
    runtime = Runtime(cfg.root, baseline) if baseline else None
    renamed = git_renames(cfg.root, baseline) if baseline else {}
    texts = {}
    def source(point, old=False):
        key = point['file'], old
        if key not in texts:
            texts[key] = (runtime._source(renamed.get(key[0], key[0])) if runtime else None) if old else read_source(cfg.root / key[0])
        return texts[key]
    def run(point, sample, old=False):
        text = source(point, old)
        file, module = point['file'], point['module']
        if old and file in renamed:         # at the baseline a moved file imported from its old place
            file, module = renamed[file], _module_at(renamed[file], file, module)
        return sealed(text, point['qual'], sample['args'], sample['kwargs'], runtime.imports(file, module, old)) \
            if text is not None else dict(status='unavailable', reason='no baseline source')
    def json_input(row):
        """A sealed comparison's input holds JSON values only: no Decimal, date or non-finite number."""
        return all(value is None or type(value) in (bool, int, str) or type(value) is float and math.isfinite(value)
                   for value in row.values())
    for name in sorted({anchor.name for anchor in index.entries if anchor.kind == 'sensor'} - compared):
        # A function owner is the reference its same-name copies are compared with.
        copies = sorted((anchor for anchor in index.named(name, 'sensor') if anchor.source_role == 'production'),
                        key=lambda anchor: not anchor.owner)
        if len(copies) < 2:
            continue
        result = _compare_pairs(cfg.root, [(copies[0], other) for other in copies[1:]], witnesses=True)
        files = {anchor.file for anchor in copies}
        new = bool(files & touched) or baseline is None
        differ = result['witnesses']
        if differ:
            points = [dict(anchor=anchor, target=anchor.target, file=anchor.file, module=anchor.module, qual=anchor.qual,
                           name=anchor.name, kind='sensor', node=None) for anchor in copies]
            lines_of = {anchor.target: f'{anchor.file}:{anchor.target_line}' for anchor in copies}
            found = compare_copies(name, points, [row for row in differ if json_input(row)], source, run, lines_of.get,
                                   no_inputs='the inputs where its copies differ are not JSON')
            if found.issue is not None:
                issues.append(found.issue)
                if found.issue.files & touched:
                    members.update(part[0] for part in found.issue.parts)
            grey = [reason.removeprefix(name + ': ') for reason in found.grey]
            if found.issue is None and not grey:
                grey = ['its copies differ on their current code, not in the closed environment']
            if grey:
                lines.append(not_compared(name, grey))
        # what kept a pair from being compared; a pair shown to differ was compared
        differing = {reason for item in result['items'] if item['changes'] for reason in item['reasons']}
        reasons = [reason.removeprefix(name + ': ') for reason in result['reasons'] if reason not in differing]
        if result['status'] == 'red' and not result['changes']:
            if new:     # copies whose declared inputs or outputs no longer match: nothing compares them
                issues.append(finding('same', f'same:{name}', f'same {name}', reasons, 'declare the same inputs and outputs on every copy',
                                      function='signature', places=tuple(f'{anchor.file}:{anchor.qual}' for anchor in copies),
                                      files=files))
        elif reasons:
            lines.append(not_compared(name, reasons))
        elif result['status'] == 'ok' and result['complete']:
            ran.add(f'same:{name}')         # every copy compared on its current code, and they agree
    return issues, lines, ran, members


def _uncovered_alone(issues, deliveries, index):
    """`issues` without the members of a `changed-alone:NAME` finding that a `same:NAME` finding of the run already
    covers (D30: one red per agreement member): a changed copy registered under NAME whose copies the same-name
    comparison found to disagree. A changed function NAME does not register stays, and so does the finding where no
    same-name finding of its name was made."""
    from dataclasses import replace
    covered = {issue.name.partition(':')[2] for part in deliveries for issue in part['issues'] if issue.family == 'same'}
    kept = []
    for issue in issues:
        name = issue.name.partition(':')[2]
        if issue.family == 'changed-alone' and name in covered:
            copies = {anchor.target for anchor in index.named(name, 'sensor')}
            parts = tuple(part for part in issue.parts if part[0] not in copies)
            if not parts:
                continue
            issue = replace(issue, parts=parts, fresh=issue.fresh & {part[0] for part in parts})
        kept.append(issue)
    return kept


def _keep_last(cfg, payload):
    """`cache.save_last` for a check that holds no map connection of its own."""
    import sqlite3
    from flowguard.map.common import cache_dir
    cache_dir(cfg.root)
    with closing(sqlite3.connect(cfg.cache / 'map.sqlite', timeout=30)) as con:
        con.execute('CREATE TABLE IF NOT EXISTS meta(k TEXT PRIMARY KEY, v TEXT)')
        with con:
            cache.save_last(con, payload)


def check(cfg, *, everything=False, since=None, deep=False, base=None, leads=False):
    """Run the one ordinary pytest route; source validation executes no code. The 4.3 block at the end: the findings
    of its pytest batch (`plugin.collect_signals().deliveries`), its own (the intent results, the comments, the
    same-name copies no batch compared) and the static ones with copy discovery (`_owner_findings`), through one
    `signals.collect`, one line per (kind, name, function); `everything` (`--all`) lists every old finding and has no
    budget, as `leads` (`--leads`, deprecated) has none. The first line counts FlowGuard's own seconds: its batch's
    and check's own work besides pytest; the lines are kept for `show --last` with that first line, and a place is
    named by the shortest end of its path that no other file of the repository has. Exit 1 for a red line only.
    Without `base` the first check of a task records HEAD as its baseline when none is recorded; a recorded one
    stays, as in pytest (`cache.task_start`)."""
    started, timing = time.time(), time.perf_counter()
    from . import deprecation, signals
    from .differences import _source_index
    from .plugin import collect_signals
    mark = deprecation.mark()
    if leads:
        deprecation.warn('check --leads', 'python -m flowguard show --last')
    start = cache.task_start(cfg, record=True) if base is None else (base, 'base', None)
    own = _Own()
    with collect_signals(everything=everything) as reports:
        _check(cfg, everything=everything, since=since, deep=deep, base=base, reports=reports, own=own)
    index = _source_index(cfg.root)
    issues, lines = _index_findings(index)
    own.issues += issues
    own.lines += lines
    found = _owner_findings(cfg, everything=everything, base=base,
                            static=reports.static.get((cfg.root, base, everything)))
    deliveries = list(reports.deliveries)
    touched = set(found.touched_files).union(*(part['touched_files'] for part in deliveries))
    # A same-name group the batch compared (a changed copy it observed, or copies it found differing) is its own.
    compared = {item['name'] for part in reports for item in part['items'] if item.get('file')}
    compared |= {issue.name.partition(':')[2] for part in deliveries for issue in part['issues'] if issue.family == 'same'}
    compared |= {name.partition(':')[2] for part in deliveries for name in part['ran'] if name.startswith('same:')}
    from .owners import baseline as owner_baseline
    issues, lines, ran, members = _same_name_findings(cfg, index, compared, touched, owner_baseline(cfg, base))
    own.issues += issues
    own.lines += lines
    own.ran |= ran
    own.touched |= members
    found.issues = _uncovered_alone(found.issues, [*deliveries, own.delivery()], index)
    lines, ignored = signals.collect([*deliveries, own.delivery()], found, everything=everything)
    if own.code and not any(line.kind == 'red' for line in lines):
        # pytest failed where no finding says why (an internal or usage error, an interruption): never a quiet pass.
        own.red('test', 'test:pytest', 'pytest', f'exit {own.code}', f'read {own.output} and correct the reported error',
                detail=own.tail)
        lines, ignored = signals.collect([*deliveries, own.delivery()], found, everything=everything)
    batch = next((part for part in reports if part.get('baseline')), None)
    baseline, kind, ahead = (batch['baseline'], batch['baseline_kind'], batch['baseline_ahead']) if batch else start
    files = git_files(cfg.root)         # the repository's files, which no shortened path of the block may name
    seconds = time.perf_counter() - timing - own.seconds + sum(part['seconds'] for part in reports)
    heading = signals.title(lines, baseline=baseline, kind=kind, ahead=ahead, option='--base', seconds=seconds)
    _keep_last(cfg, signals.last_run(lines, ignored, run='check', stamp=started, baseline=baseline, kind=kind, title=heading,
                                     seconds=seconds, deprecated=deprecation.used(mark), hidden=found.hidden))
    status = int(any(line.kind == 'red' for line in lines))
    _show_signals(signals.render_block(lines, title=heading, everything=everything or leads, files=files), status)
    return status


def _show_signals(text, status):
    """The block on the console, as at the end of an ordinary test run."""
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


def static_check(cfg, *, everything=False, base=None, leads=False):
    """`check --static`: the map checks alone, without pytest: the fallback ledger, owner writes and pairs,
    values outside declared sets, new spellings, unchanged copies, deletes that leave children, missing columns,
    the catalog and touched structure problems (`owners.static_findings`), with the flowguard comments, as the 4.3
    block (`signals.collect`, `render_block`). Only what this change adds is red; `everything` (`--all`) lists every
    old finding as before and has no budget, as `leads` (`--leads`, deprecated) has none. The first line always
    prints, with the whole command's seconds; the lines are kept for `show --last`, and a place is named by the
    shortest end of its path that no other file of the repository has. With FLOWGUARD_LINES set (the static test
    inside a vitest run, `NPM_CHECK`) the payload `show --last` keeps (`signals.last_run`) and the parts of its first
    line (`title_parts`, the keywords of `signals.title`) go to that JSON file for the vitest report's block, and
    nothing to stdout. Exit 1 for a red line only. Without `base` the first run of a task records HEAD as its
    baseline when none is recorded; a recorded one stays, as in pytest (`cache.task_start`); the title names it as
    pytest does."""
    started, timing = time.time(), time.perf_counter()
    from . import anchors, deprecation, ledger as fallbacks, owners, signals
    mark = deprecation.mark()
    if leads:
        deprecation.warn('check --leads', 'python -m flowguard show --last')
    start = cache.task_start(cfg, record=True) if base is None else (base, 'base', None)
    with closing(build(cfg.root, roots=cfg.roots)) as graph:
        index = anchors.collect(graph)
        found = owners.static_findings(cfg, graph, index, base, everything=everything)
        baseline = owners.baseline(cfg, base)
        result = fallbacks.evaluate(cfg, graph, baseline=baseline) if fallbacks.path(cfg).is_file() \
            else fallbacks.absent(cfg, baseline)
        comments, unparsed = _index_findings(index)
        ledger_reds, later, ran = _ledger_findings(result)
        legacy = _legacy_lines(fallbacks.open_legacy(cfg, graph)) if everything else []
        lines, ignored = signals.collect([signals.delivery([*comments, *ledger_reds], [*unparsed, *later, *legacy], ran=ran)],
                                         found, everything=everything)
        target = os.environ.get('FLOWGUARD_LINES')       # the static test inside a vitest run (NPM_CHECK)
        files = frozenset() if target else git_files(cfg.root)      # the vitest report prints these lines
        seconds = time.perf_counter() - timing
        parts = dict(baseline=start[0], kind=start[1], ahead=start[2], option='--base')
        heading = signals.title(lines, **parts, seconds=seconds)
        payload = signals.last_run(lines, ignored, run='check --static', stamp=started, baseline=start[0], kind=start[1],
                                   title=heading, seconds=seconds, deprecated=deprecation.used(mark), hidden=found.hidden)
        with graph.con:
            cache.save_structure(graph.con, found.summary)
            cache.save_last(graph.con, payload)
    status = int(any(line.kind == 'red' for line in lines))
    if target:
        # the vitest report reads this file (`vitest.static_lines`): the payload show --last reads, and the parts of
        # its first line (`signals.title`)
        target = Path(target)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(dict(payload, title_parts=parts), ensure_ascii=False, sort_keys=True), encoding='utf-8')
    else:
        _show_signals(signals.render_block(lines, title=heading, everything=everything or leads, files=files), status)
    return status


def _owner_findings(cfg, *, everything=False, base=None, static=None):
    """Owners, copies and static findings of this change; copy discovery runs only here, in check. `everything`
    (`--all`) adds the before lines of the ledger's open legacy handlers (`_legacy_lines`)."""
    from . import anchors, owners
    if not owners.baseline(cfg, base) and not everything:
        return owners.Findings()            # nothing is new without a baseline; the old ledger is check --all
    with closing(build(cfg.root, roots=cfg.roots)) as graph:
        index = anchors.collect(graph)
        distincts = cache.read(cfg)['summary'].get('distincts', [])
        excluded = {target for item in distincts for target in (item['a'], item['b']) if ':' in target}
        excluded |= {anchor.target for item in distincts for name in (item['a'], item['b']) for anchor in index.named(name)}
        found = owners.check_findings(cfg, graph, index, base, everything=everything, excluded=excluded, static=static)
        if everything:
            from .ledger import open_legacy
            found.lines = [*found.lines, *_legacy_lines(open_legacy(cfg, graph))]
        with graph.con:
            cache.save_structure(graph.con, found.summary)
        return found


def _check_selection(cfg: Config, model: object, data: dict, everything: bool, since: str | None, sentinel: Path,
                     base: str | None = None):
    import ast
    from flowguard.map.common import git_run
    from . import deps, history
    with closing(build(cfg.root, roots=cfg.roots)) as graph:
        # The commit pytest compares with (its Runtime resolves --flowguard-base the same way), else the task
        # baseline: a source judged against another commit (`baseline:<commit>` of deps.record) is judged again.
        commit = None if base is None else git_run(cfg.root, 'rev-parse', '--verify', base + '^{commit}').stdout.decode().strip()
        now = deps.Now(cfg, graph, baseline=commit)
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


def _check(cfg, *, everything=False, since=None, deep=False, base=None, reports=None, own=None):
    """The pytest part of `check`: select the affected rules and tests, run them in one pytest batch (its findings
    reach `reports`, `plugin.collect_signals`) and add check's own findings to `own` (`_Own`): the intent results it
    ran or reused (`_cache_findings`), the history of the intent rules, the ledger when no intent item runs, and an
    unfinished batch; `own.code` is the batch's pytest exit code."""
    import ast
    from . import history
    from .loader import load
    stream_all = everything
    model = load(cfg)
    model.deep = deep
    historical = history.check(cfg, base)
    data = cache.read(cfg)
    retry_incomplete = bool((data.get('attempt') or {}).get('errors'))
    if not model.declared_items() and not everything and not retry_incomplete:
        # No intent item runs, so the ledger the plugin would report is compared here without pytest.
        from .owners import baseline as owner_baseline
        issues, lines, ran = _ledger_findings(_ledger_result(cfg, owner_baseline(cfg, base)))
        own.issues += issues
        own.lines += lines          # a [structure] entry of a later FlowGuard: not compared, as in pytest
        own.ran |= ran
        own.history(historical)
        return 0
    sentinel = cfg.root / 'tests/test_flowguard_intent.py'
    if model.declared_items() and not sentinel.is_file():
        own.red('input', 'sentinel:missing', 'sentinel', f'{cfg.rel(sentinel)} is missing', 'run python -m flowguard init',
                places=(cfg.rel(sentinel),))
        return 0
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
        cfg, model, data, everything, since, sentinel, base)
    extras = flows
    attempt = data.get('attempt') or {}
    failed_collection = (attempt.get('sentinel') is not None or attempt.get('collected')) and (
        attempt.get('missing') or attempt.get('sentinel') != 'ok')
    run = everything or selected or extras or ordinary or model.errors or failed_collection or not data.get('collection')
    executed = set()
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
        started, timing = time.time(), time.perf_counter()
        process = _run_check_pytest(batch, cfg.root, output, stream_all)
        own.seconds += time.perf_counter() - timing
        process_code = own.code = process.returncode
        own.output = cfg.rel(output)
        actual = [line for line in (process.stdout + process.stderr).splitlines() if line.strip()]
        own.tail = [line for line in actual if line.startswith('FlowGuard:')] or actual[-5:]
        data = cache.read(cfg)
        executed.update(selected)
        if not model.declared_items():
            own.history(historical)
            return process_code
        if not data.get('attempt') or data['attempt'].get('stamp', 0) < started:
            own.red('test', 'test:pytest', 'pytest', 'did not finish', f'read {own.output} and correct the reported error')
            return process_code
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
    from .owners import baseline as owner_baseline
    revision = owner_baseline(cfg, base)
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
        with closing(build(cfg.root, roots=cfg.roots)) as graph:
            for rid, found in proofs.items():
                cache.save_proven(graph.con, model.rules[rid], found)
            graph.con.commit()
        data = cache.read(cfg)
    for group in data['results'].values():
        group['items'] = {item: value for item, value in group['items'].items() if item in declared}
    data['summary']['errors'].extend(error for error in model.errors if error not in data['summary']['errors'])
    data['history'] = historical
    issues, lines = _cache_findings(cfg, model, data)
    own.issues += issues + (_owner_rules_unverified(cfg, data) if stream_all else [])
    own.lines += lines
    own.ran |= _judged_names(model, data)
    return process_code


def _owner_rules_unverified(cfg, data):
    """check --all: a rule quoting the owner's words that stays grey is red (D7), unless the ledger's [unverified]
    section lists it with a reason; one finding per rule."""
    from . import ledger
    from .api import IntentError
    from .signals import ascii_text, finding
    from .sources import cited, parse
    listed = ledger.unverified(cfg)[0]
    issues = []
    for rid, item in data['summary']['rules'].items():
        result = data['results'].get(rid, {})
        # The --deep mutation probe (`live`) measures how tightly the tests bind a rule, not whether the rule
        # was checked: a `fields` anchor cannot be called directly by it, and its rule is still verified.
        checked = dict(result, items={key: value for key, value in result.get('items', {}).items()
                                      if value.get('kind') != 'live'})
        if item.get('superseded_by') or _rule_colour(item, checked) != 'grey' or rid in listed:
            continue
        try:
            source = cited(parse(item.get('source', '')), cfg)     # rule.<id>: the words its rules.toml entry cites
        except IntentError:
            continue        # The load check reports an unreadable source.
        if source.kind not in ('owner', 'request'):
            continue
        reasons = [ascii_text(message) for value in result.get('items', {}).values() for message in value.get('grey', ())]
        # The line names no way to silence it (design 4.7): the grey reasons, with their own steps, and the owner's
        # alternative, a reason in the ledger, are its detail.
        issues.append(finding('rule', f'unverified:{rid}', f'rule {rid}',
                              [f'cites original words from the owner ({source.rids[0]}), but is now grey (unverified): '
                               + (reasons[0].partition(' -> ')[0] if reasons else 'no results yet')],
                              'restore observability so the rule is checked again',
                              detail=[*reasons, f"only with the owner's yes: in {ledger.LEDGER} [unverified] section, write a reason: "
                                                f'{rid} = {ledger._quote(ledger.PLACEHOLDER_UNVERIFIED)}']))
    return issues


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


NPM_HEADER = INIT_MARK + ': FlowGuard\'s map checks inside `npm test`.'
NPM_CHECK = NPM_HEADER + '''
// It does one thing: run `python -m flowguard check --static` at the project root and fail when anything is red
// (exit 1) or FlowGuard cannot run. Its lines are FlowGuard's block: in a run of FlowGuard's test runner plugin
// (FLOWGUARD_VITEST_OBS set) they go to that run's static.json, which the plugin prints in its block after the
// summary; otherwise this test prints them. On red it fails with one line that points at the block.
// Python is found in this order:
//   1. the FLOWGUARD_PYTHON environment variable, when set (then only that one);
//   2. the interpreter that ran `flowguard init` on this machine, recorded in @RECORDED@ (git-ignored);
//   3. `python3`, `python` and, on Windows, `py -3` on PATH.
// The first that can import flowguard runs the check; when none can, the test fails and lists what was tried.
@IMPORTS@
const ROOT = @ROOT@;
const RECORDED = path.join(ROOT, ...@RECORDED@.split('/'));

function interpreters() {
  if (process.env.FLOWGUARD_PYTHON) return [[process.env.FLOWGUARD_PYTHON]];
  const listed = fs.existsSync(RECORDED) ? [[fs.readFileSync(RECORDED, 'utf8').trim()]] : [];
  listed.push(['python3'], ['python']);
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

function reds(lines, stdout) {
  // The red lines the check found: those of static.json, or the count on the block's first line.
  if (lines !== null) {
    return fs.existsSync(lines) ? JSON.parse(fs.readFileSync(lines, 'utf8')).lines.filter((line) => line.kind === 'red').length : 0;
  }
  const first = /^FlowGuard \\d+\\.\\d+ \\(.*\\): (\\d+) red[,;]/m.exec(stdout);
  return first ? Number(first[1]) : 0;
}

test('FlowGuard check --static', () => {
  const python = findPython();
  if (python.command === null) {
    throw new Error('FlowGuard: no Python that can import flowguard was found; set FLOWGUARD_PYTHON to the interpreter '
      + 'FlowGuard is installed in. Tried:\\n' + python.tried.join('\\n'));
  }
  const observations = process.env.FLOWGUARD_VITEST_OBS;
  const lines = observations ? path.join(observations, 'static.json') : null;
  const env = { ...process.env, PYTHONIOENCODING: 'utf-8' };
  if (lines !== null) {
    env.FLOWGUARD_LINES = lines;
    fs.rmSync(lines, { force: true });        // never the lines of an earlier run
  }
  const run = spawnSync(python.command, [...python.prefix, '-m', 'flowguard', 'check', '--static'], {
    cwd: ROOT, encoding: 'utf8', maxBuffer: 64 * 1024 * 1024, env,
  });
  const stdout = (run.stdout || '').trimEnd();
  const output = ((run.stdout || '') + (run.stderr || '')).trimEnd();
  if (lines === null) {
    if (output) console.log(output);
  } else if ((run.stderr || '').trim()) {
    console.error((run.stderr || '').trimEnd());
  }
  if (run.error) throw run.error;
  const red = run.status === 1 ? reds(lines, stdout) : 0;
  if (red > 0) throw new Error('FlowGuard: ' + red + ' red, see the FlowGuard block at the end');
  if (run.status !== 0) {
    throw new Error('FlowGuard check --static exit ' + run.status + (output ? ':\\n' + output : ''));
  }
}, 600000);
'''


# The scripts init reads as test suites, and the unit suite names it wires before any other (`test:unit`, `unit`).
_TEST_SCRIPT = re.compile(r'test(?:[:_-].+)?|unit')
_UNIT_SCRIPT = re.compile(r'(?:test[:_-])?unit')
# Suites that reach real databases and services: init leaves their scripts as they are. A script is one when a
# part of its name (split on : _ -) or a folder of a path it runs (split on /) is one of these words or starts
# with `integration`.
_OTHER_SUITES = {'int', 'it', 'e2e', 'db', 'database', 'smoke', 'acceptance', 'perf', 'performance', 'load', 'bench',
                 'benchmark'}
# Options of vitest and jest whose value is the next word (unless written `--option=value`); the others are flags.
_VALUED = {'-c', '--config', '-r', '--root', '--dir', '--project', '-t', '--testNamePattern', '--reporter', '--outputFile',
           '--environment', '--pool', '--shard', '--mode', '--exclude', '--testPathPattern', '--testPathPatterns',
           '--selectProjects', '--rootDir', '--roots', '--projects', '--ignoreProjects', '--workspace', '--changedSince',
           '--testMatch', '--testRegex', '--testPathIgnorePatterns'}
# Options that choose the files or tests a call runs from something init does not read (its own root or folder, a
# config, a project, test names, a shard, changed or related files): init cannot tell whether such a call runs a
# file at the package root, and a file named on it may still not run.
_ELSEWHERE = {'-r', '--root', '--dir', '--rootDir', '--roots', '-c', '--config', '--project', '--projects',
              '--selectProjects', '--ignoreProjects', '--workspace', '-t', '--testNamePattern', '--shard', '--changed',
              '-o', '--onlyChanged', '--changedSince', '--lastCommit', '--findRelatedTests', '-f', '--onlyFailures',
              '--testPathPattern', '--testPathPatterns', '--testMatch', '--testRegex'}
_WATCH = {'--watch', '--watchAll'}
# Options init knows to leave the files a call runs as they are: reporting, workers, timeouts, coverage, caching.
# A call with any other option is one init cannot read: it neither wires nor names it as running a file.
_SAFE = {'--run', '--passWithNoTests', '--silent', '--coverage', '--no-coverage', '--globals', '--isolate', '--no-isolate',
         '--no-file-parallelism', '--fileParallelism', '--ci', '--runInBand', '-i', '--verbose', '--colors', '--no-colors',
         '--color', '--no-color', '--json', '--detectOpenHandles', '--forceExit', '-u', '--update', '--no-cache',
         '--logHeapUsage', '--allowOnly', '--hideSkippedTests', '--clearMocks', '--reporter', '--reporters', '--outputFile',
         '--coverageReporters', '--coverageDirectory', '--watchman', '--no-watchman', '--pool', '--environment',
         '--maxWorkers', '--minWorkers', '--testTimeout', '--hookTimeout', '--bail', '--mode', '--maxConcurrency', '--retry',
         '--logLevel'}
_SAFE_PREFIXES = ('--coverage.', '--reporter.', '--outputFile.', '--sequence.', '--poolOptions.')
# Safe options whose value is the next word unless written `--option=value`.
_SAFE_VALUED = {'--reporter', '--outputFile', '--coverageDirectory', '--pool', '--environment', '--maxWorkers',
                '--minWorkers', '--testTimeout', '--hookTimeout', '--mode', '--maxConcurrency', '--retry', '--logLevel'}
# jest's array options (yargs): every word after one, up to the next option, is a value, also after `--reporters=x`.
_JEST_ARRAYS = {'--reporters', '--coverageReporters'}
# vitest's options with an optional value (`-u [type]`): the next word, unless it is an option.
_VITEST_OPTIONAL = {'-u', '--update'}
# The words vitest's --silent takes (vitest 3.1 on refuse any other word after it, `--silent tests/unit`, where vitest
# 3.0 and earlier read a flag and then a path): the next word only when it is one of them.
_SILENT = ('true', 'yes', 'false', 'no', 'passed-only')
# The prefixed options vitest 2 to 5 all read as booleans; every other prefixed option (`--coverage.include src`) has a
# value, except the ones below.
_PREFIXED_FLAGS = re.compile(r'--coverage\.(?:enabled|clean|cleanOnRerun|reportOnFailure|allowExternal|skipFull'
                             r'|thresholds\.100)|--sequence\.(?:shuffle(?:\.files|\.tests)?|concurrent)')
# Prefixed options vitest versions read differently, a boolean in some (the next word is a path) and a value in others
# (the next word is that value): vitest 3's --coverage.all and poolOptions booleans, which vitest 4 dropped (an option
# vitest does not know takes the next word), --coverage.thresholds.autoUpdate (a value from vitest 4),
# --coverage.thresholds.perFile (from vitest 5) and vitest 5's new booleans. They take true, yes, false or no; a call
# that gives one another word is one init cannot read.
_PREFIXED_VERSIONED = re.compile(r'--coverage\.(?:all|thresholds\.(?:autoUpdate|perFile)|excludeAfterRemap'
                                 r'|autoAttachSubprocess)|--poolOptions\.\w+\.(?:isolate|singleThread|singleFork|useAtomics)')
# The file a runner's package starts it from when a script calls it through node (`node node_modules/jest/bin/jest.js`).
_RUNNER_FILES = {'jest': 'jest.js', 'vitest': 'vitest.mjs'}
# Commands a shell finds without npx: node and the package managers; npx runs any other word of a call.
_LAUNCHERS = {'node', 'npx', 'pnpm', 'pnpx', 'yarn', 'bun', 'bunx'}
# node's flag jest needs to load ES module tests, and jest's documented call with it.
_VM = '--experimental-vm-modules'
_JEST_ESM = f'node {_VM} node_modules/jest/bin/jest.js'
# Options that make a call wait for a debugger before it runs (node's, also in NODE_OPTIONS, and vitest's).
_DEBUGGER = re.compile(r'--inspect-(?:brk|wait)\b|--inspectBrk\b')


def _alone(prefix, name):
    """The call that runs the generated test file `name` alone, started the way `prefix` starts the runner (the
    words of a script's call up to the runner, and vitest's `run`: `vitest run`, `node --experimental-vm-modules
    node_modules/jest/bin/jest.js`)."""
    return f'{prefix} {name}'


def _vm_scripts(scripts):
    """The scripts that run under node's --experimental-vm-modules: those whose command names the flag
    anywhere (`NODE_OPTIONS=... jest`, `export NODE_OPTIONS=... && jest`, Windows' `set NODE_OPTIONS=... &&
    jest`), and the scripts such a command runs (`npm run test:jest`, `pnpm run x`, `yarn x`), which inherit its
    environment."""
    found = {name for name, command in scripts.items() if isinstance(command, str) and _VM in command}
    pending = list(found)
    while pending:
        command = scripts[pending.pop()]
        for other in re.findall(r'\b(?:npm|pnpm|yarn)(?:\s+run(?:-script)?)?\s+([\w:.-]+)', command):
            if other in scripts and other not in found:
                found.add(other)
                pending.append(other)
    return found


def _vm_launch(prefix):
    """How a line for another script starts jest with node's --experimental-vm-modules, from a call's `prefix`
    (its words up to the runner): its `cross-env`, its NODE_OPTIONS setting reduced to that flag, `node` with
    that flag alone, and the runner. The call's other settings (a database URL) and node flags (a debugger that
    waits, a heap size) belong to it alone. A call that passes the flag another way gives jest's documented call."""
    words = re.findall(r'(?:[^\s"\']+|"[^"]*"|\'[^\']*\')+', prefix)
    kept = [f'NODE_OPTIONS={_VM}' if word.startswith('NODE_OPTIONS=') else word for word in words[:-1]
            if word in ('cross-env', 'node', _VM) or word.startswith('NODE_OPTIONS=') and _VM in word]
    return ' '.join([*kept, words[-1]]) if any(_VM in word for word in kept) else _JEST_ESM


def _from_shell(call):
    """`call` as a shell outside npm runs it: npm puts node_modules/.bin on PATH, so the first word after the
    leading `NAME=value` settings goes through npx unless it is node or a package manager."""
    for word in re.finditer(r'(?:[^\s"\']+|"[^"]*"|\'[^\']*\')+', call):
        if re.match(r'[A-Za-z_]\w*=', word.group()):
            continue
        return call if word.group() in _LAUNCHERS else call[:word.start()] + 'npx ' + call[word.start():]
    return call


def _takes(option, runner):
    """How `option` of `runner` takes the word after it (unless written `--option=value`): 'next' always as its
    value, 'word' unless it is an option, 'every' with each word after it up to the next option (also after
    `--option=value`), 'silent' only one of `_SILENT`, 'versioned' only true, yes, false or no (another word
    leaves the call unread, `_PREFIXED_VERSIONED`), 'flag' only `true` or `false` (a `--no-` option none;
    `--bail` also a number)."""
    if runner == 'jest' and option in _JEST_ARRAYS:
        return 'every'
    if runner == 'vitest' and option == '--silent':
        return 'silent'
    if _PREFIXED_VERSIONED.fullmatch(option):
        return 'versioned'
    if option in _VALUED or option in _SAFE_VALUED or runner == 'jest' and option == '-w':
        return 'next'
    if runner == 'vitest' and option in _VITEST_OPTIONAL or option.startswith(_SAFE_PREFIXES) \
            and not _PREFIXED_FLAGS.fullmatch(option):
        return 'word'
    return 'flag'


class _Call(typing.NamedTuple):
    """A call of the runner in a script (see _runner_calls)."""
    text: str
    watches: bool
    options: set
    paths: list
    clear: bool
    unread: set
    prefix: str
    end: int


def _runner_calls(command, runner):
    """Each call of `runner` in a script (`a && b`, `a; b` and `a || b` are calls of their own; the runner is a
    word named `runner` or its package's start file, `node_modules/jest/bin/jest.js`): its text, whether it
    watches, its options, its paths (`./` taken off; `.` is the package folder, spelled ''), whether init can
    read it (`clear`: every option is one of `_SAFE` or a watch option, and no option vitest versions read
    differently is given a word they read differently), the options it cannot read (`unread`), its prefix (its
    words up to the runner, then vitest's `run`) and where in its text a file added to it goes: at its end, or
    after its last path when its last option could take that file as its value (`vitest run tests -u`, `vitest
    run tests --silent`, `jest tests --reporters=default`). An option's value (`_takes`) is never a path:
    `--coverage.include src`, `-u tests` and vitest's `--silent passed-only` run every file, `--silent tests/unit`
    runs tests/unit. `--watch=false` and `--watchAll false` turn watching off; `vitest watch`, `vitest dev` and
    vitest's `-w` watch (jest's `-w` is its worker count)."""
    watch = _WATCH | ({'-w'} if runner == 'vitest' else set())
    safe = _SAFE | ({'-w'} if runner == 'jest' else set())
    calls = []
    for segment in re.split(r'&&|\|\||;', command):
        words = list(re.finditer(r'\S+', segment))
        at = next((index for index, word in enumerate(words)
                   if word.group().rpartition('/')[2] in (runner, _RUNNER_FILES[runner])), None)
        if at is None or [word.group() for word in words[at + 1:at + 2]] == ['related']:
            continue
        rest = words[at + 1:]
        verb = rest[0].group() if rest and rest[0].group() in ('run', 'watch', 'dev') else ''
        options, paths, pending, watches, last, unsure = set(), [], None, verb in ('watch', 'dev'), None, set()
        for match in rest[1:] if verb else rest:
            word = match.group()
            if pending is not None:
                option, takes = pending
                pending = pending if takes == 'every' else None
                if takes == 'next' or takes in ('word', 'every') and not word.startswith('-') or takes == 'flag' and (
                        word in ('true', 'false') and not option.startswith('--no-')
                        or option == '--bail' and word.isdigit()) or takes == 'silent' and word in _SILENT \
                        or takes == 'versioned' and word in ('true', 'yes', 'false', 'no'):
                    if option in watch:
                        watches = word == 'true'
                    continue
                if takes == 'versioned' and not word.startswith('-'):
                    unsure.add(option)
                pending = None
            if word.startswith('-'):
                option, equals, value = word.partition('=')
                options.add(option)
                if option in watch:
                    watches = value != 'false' if equals else True
                takes = _takes(option, runner)
                pending = (option, takes) if takes == 'every' or not equals else None
            else:
                last = match
                while word.startswith('./'):
                    word = word[2:]
                paths.append('' if word in ('.', '') else word.rstrip('/'))
        clear = not unsure and all(option in safe or option in watch or option.startswith(_SAFE_PREFIXES) for option in options)
        unread = unsure | {option for option in options if option not in _SAFE and not option.startswith(_SAFE_PREFIXES)}
        prefix = segment[words[0].start():words[at].end()] + (' run' if runner == 'vitest' else '')
        opened = pending is not None and pending[1] != 'flag' and last is not None
        calls.append(_Call(segment, watches, options, paths, clear, unread, prefix,
                           last.end() if opened else len(segment.rstrip())))
    return calls


def _filtered_scripts(cfg, package, runner, name, launch, vm, vm_scripts=frozenset()):
    """What init did to the test suite scripts (`test`, `test:unit`, `unit`, ...) so one of them runs `name`;
    the script that runs it (None when init can tell of none); and the watch scripts or other suites that run it.
    init reads a call only when every option it has is one it knows to leave the files alone (`_SAFE`:
    reporters, workers, timeouts, coverage; `_runner_calls` `clear`); a call with any other option (its own
    root or config, a project, test names, ignore patterns, an option init does not know) may run any files, so
    init neither wires it nor names it as running `name`. A script runs `name` when a call init reads names it
    or runs every file (no path, or the package folder). Watch scripts (a name part `watch`, `--watch`, vitest's
    `-w`, `vitest watch`) and integration, end-to-end, database, smoke, acceptance, performance, load or
    benchmark suites (real databases and services; by a part of the name or a folder they run) are never wired
    and never named as the script that runs it, nor are debug scripts (a name part `debug`, or a call that waits
    for a debugger: `--inspect-brk`). With `vm` (jest loads `name`, an ES module, only under node's
    --experimental-vm-modules) a call without that flag cannot run it and counts as no call. A script that runs the runner on named folders only (`vitest
    run tests/unit`) skips a test at the package root, so `name` is added to one such script: `test` (what npm
    test runs) first, then `test:unit`, `test-unit`, `test_unit` and `unit`, then other unit names, then shorter
    names, then the order of the file. The check covers the whole repository, so one script is enough: nothing
    is added when a call init reads already names `name`. A script init cannot edit without touching the rest of
    the file is named with the edit to make, and the next one is tried. A script init cannot read is named with
    the edit to make when it is `test`, runs named paths, or when nothing runs `name`; the other suites init left alone are
    named when nothing runs it. A script that runs single files is a check of its own and stays as it is. `name`
    goes where `_runner_calls` says, so no option takes it as its value. The edit named for a script starts the
    runner the way that script's call does (its prefix); the other lines start it with `launch`."""
    text = package.read_text(encoding='utf-8-sig')
    scripts = json.loads(text).get('scripts') or {}
    named, runners, excluded, others, tried, unread = False, [], [], [], [], []
    for index, (script, command) in enumerate(scripts.items()):
        calls = [call for call in _runner_calls(command, runner) if not vm or script in vm_scripts or _VM in call.prefix] \
            if isinstance(command, str) and _TEST_SCRIPT.fullmatch(script) else []
        if not calls:
            continue
        words = re.split(r'[:_-]', script.lower())
        folders = [folder for call in calls for path in call.paths for folder in path.lower().split('/')]
        clear = [call for call in calls if call.clear]
        names = any(name in call.paths for call in clear)
        named = named or names
        runs = names or any(not call.paths or '' in call.paths for call in clear)
        if any(part.startswith('integration') or part in _OTHER_SUITES for part in words + folders):
            (excluded if runs else others).append(script)
            continue
        if 'watch' in words or 'debug' in words or any(call.watches or _DEBUGGER.search(call.text) for call in calls):
            if runs:
                excluded.append(script)
            continue
        rank = (script != 'test', not _UNIT_SCRIPT.fullmatch(script.lower()),
                not any(word.startswith('unit') for word in words), len(script), index)
        if runs:
            runners.append((rank, script))
            continue
        wire = next((call for call in clear if call.paths and all((package.parent / path).is_dir() for path in call.paths)),
                    None)
        if wire is not None:
            tried.append((rank, script, command, wire.text, wire.end))
        if len(clear) < len(calls):
            options = sorted({option for call in calls if not call.clear for option in call.unread})
            prefix = next(call.prefix for call in calls if not call.clear)
            unread.append((rank, script, command, options, any(call.paths for call in calls), prefix))
    call = _alone(launch, name)
    lines, wired = [], None
    for rank, script, command, segment, end in [] if named else sorted(tried):
        where = f'{cfg.rel(package)} script "{script}"'
        new = command.replace(segment, segment[:end] + ' ' + name + segment[end:], 1)
        spelled = re.compile(r'(' + re.escape(json.dumps(script)) + r'\s*:\s*)' + re.escape(json.dumps(command)))
        if len(spelled.findall(text)) != 1:
            lines.append(f'{where} runs {runner} on named paths only: change it to {new} so it runs {name} too')
            continue
        package.write_text(spelled.sub(lambda match: match.group(1) + json.dumps(new), text), encoding='utf-8')
        lines.append(f'{where} runs {runner} on named paths only; init added {name}: {new}')
        runners.append((rank, script))
        wired = script
        break
    for _, script, command, options, has_paths, prefix in [] if named else sorted(unread):
        if has_paths or not runners or script == 'test':           # npm test's own script is always worth the line
            lines.append(f'{cfg.rel(package)} script "{script}" runs {runner} with {", ".join(options)}, which init does not '
                         f'read ({command}): init cannot tell whether it runs {name}; if it does not, add '
                         f'"&& {_alone(prefix, name)}" to it yourself')
    if not runners and others:
        left = ', '.join('"' + script + '"' for script in others)
        lines.append(f'{cfg.rel(package)} script {left} runs {runner} on an integration, end-to-end or other suite that '
                     'reaches real databases and services: init leaves it alone; to run the check with it, '
                     f'add "&& {call}" to it yourself' if len(others) == 1 else
                     f'{cfg.rel(package)} scripts {left} run {runner} on integration, end-to-end or other suites that '
                     'reach real databases and services: init leaves them alone; to run the check with one of them, '
                     f'add "&& {call}" to it yourself')
    return lines, min(runners)[1] if runners else None, excluded


def _npm_check(cfg, package):
    """Write the vitest (or, for a jest project, jest) test that runs `check --static`; returns what it did."""
    data = json.loads(package.read_text(encoding='utf-8-sig'))
    if not isinstance(data, dict):
        raise ValueError(f'{package}: package.json is not a JSON object')
    named = {**(data.get('dependencies') or {}), **(data.get('devDependencies') or {})}
    scripts = {name: str(command) for name, command in (data.get('scripts') or {}).items()}
    script = scripts.get('test', '')
    if not {'vitest', 'jest'} & set(named) and not any(re.search(r'\b(?:vitest|jest)\b', command) for command in scripts.values()):
        return (f'{cfg.rel(package)} names no test runner (vitest or jest in its dependencies or scripts): no FlowGuard '
                'test is written there; the check of another package covers the whole repository.')
    runner = 'jest' if ('jest' in named or 'jest' in script) and 'vitest' not in named and 'vitest' not in script else 'vitest'
    # jest loads a test as an ES module only under node's --experimental-vm-modules, and every test as CommonJS
    # without it, whatever the package's type: the test of a "type": "module" package is an ES module when a script
    # runs jest with that flag (in its own call, an earlier `export`/`set NODE_OPTIONS=` of the script, or a script
    # that runs it: `_vm_scripts`), or none runs jest at all; when its scripts run jest only without it, CommonJS.
    under_vm = _vm_scripts(scripts)
    calls = [call for command in scripts.values() for call in _runner_calls(command, runner)]
    vm_calls = [call for script_name, command in scripts.items() for call in _runner_calls(command, runner)
                if script_name in under_vm or _VM in call.prefix]
    vm = runner == 'jest' and data.get('type') == 'module' and (not calls or bool(vm_calls))
    module = runner == 'vitest' or vm
    target = package.parent / ('flowguard.static.test.mjs' if runner == 'vitest' else 'flowguard.static.test.js')
    relative = os.path.relpath(cfg.root, package.parent).replace(os.sep, '/')
    if module:
        imports = ("import { test } from 'vitest';\n" if runner == 'vitest' else '') + \
            ("import { spawnSync } from 'node:child_process';\nimport fs from 'node:fs';\nimport path from 'node:path';\n"
             "import { fileURLToPath } from 'node:url';")
        root = f"path.resolve(path.dirname(fileURLToPath(import.meta.url)), {json.dumps(relative)})"
    else:
        imports = "const { spawnSync } = require('node:child_process');\nconst fs = require('node:fs');\nconst path = require('node:path');"
        root = f'path.resolve(__dirname, {json.dumps(relative)})'
    text = (NPM_CHECK.replace('@IMPORTS@', imports).replace('@ROOT@', root)
            .replace('@RECORDED@', json.dumps(RECORDED_PYTHON)))
    if target.exists() and not target.read_text(encoding='utf-8').startswith(NPM_HEADER):
        raise ValueError(f'{target}: an existing file has this name; rename it, then run init again')
    target.write_text(text, encoding='utf-8', newline='\n')
    # How the advice starts the runner: as is, but an ES module test of jest under --experimental-vm-modules, the
    # way the first script that does so starts it (`_vm_launch`), else as jest's own documentation spells it.
    launch = 'vitest run' if runner == 'vitest' else 'jest'
    if vm:
        launch = next((_vm_launch(call.prefix) for call in vm_calls if _VM in call.prefix), _JEST_ESM)
    lines, runs, excluded = _filtered_scripts(cfg, package, runner, target.name, launch, vm, under_vm)
    # The line names the script that runs the file: npm test only when the "test" script itself runs it, and never
    # a watch script or a suite that reaches real databases and services.
    if runs is None:
        left = ', '.join('"' + script + '"' for script in excluded)
        found = (f'in {cfg.rel(package)} only {left} {"runs" if len(excluded) == 1 else "run"} it, and init names no watch '
                 'or debug script, nor a suite that reaches real databases and services' if excluded else
                 f'init finds no script in {cfg.rel(package)} that runs it')
        call = _alone(launch, target.name)
        static = (f'Generated {cfg.rel(target)} ({runner}), but {found}: add "&& {call}" to the script you run your tests '
                  f'with, so it runs python -m flowguard check --static and fails on red ({_from_shell(call)} runs it alone).')
    else:
        static = (f'Generated {cfg.rel(target)} ({runner}): {"npm test" if runs == "test" else "npm run " + runs} runs '
                  'python -m flowguard check --static and fails on red.')
    static += ''.join('\n' + line for line in lines)
    if runner == 'jest':
        return static + '\nThe execution side supports vitest only: this jest project runs check --static alone.'
    from .vitest import wire
    return static + '\n' + wire(cfg, package)


# The conftest lines init wrote before 4.2, when it registered the plugin a second time beside addopts.
CONFTEST_PLUGIN = ('pytest_plugins = ["flowguard.intent.plugin"]\n',
                   'pytest_plugins = ([pytest_plugins] if isinstance(pytest_plugins, str) else list(pytest_plugins)) + ["flowguard.intent.plugin"]\n')


def _pytest_config(root, pyproject_text):
    """The file pytest reads its options from when that is not pyproject.toml, else None: pytest.toml or
    .pytest.toml (pytest 9), pytest.ini or .pytest.ini, or tox.ini/setup.cfg with a pytest section while
    pyproject.toml has none (pytest's order)."""
    for name in ('pytest.toml', '.pytest.toml', 'pytest.ini', '.pytest.ini'):
        if (root / name).is_file():
            return name
    if re.search(r'^\[tool\.pytest\.ini_options\]', pyproject_text, re.M):
        return None
    for name, section in (('tox.ini', 'pytest'), ('setup.cfg', 'tool:pytest')):
        path = root / name
        if path.is_file() and re.search(r'^\[' + re.escape(section) + r'\]', path.read_text(encoding='utf-8-sig'), re.M):
            return name
    return None


def _register_plugin(cfg, conftest, text):
    """The pyproject.toml text with the plugin registered once: in pytest's addopts when pyproject.toml is
    pytest's configuration (it loads before any conftest), else in the sentinel's conftest.py. A conftest
    line an earlier init wrote beside addopts is removed."""
    content = conftest.read_text(encoding='utf-8') if conftest.exists() else ''
    if _pytest_config(cfg.root, text) is None:
        kept = content
        for line in CONFTEST_PLUGIN:
            kept = kept.replace('\n\n' + line, '\n').replace(line, '')
        if kept != content and kept.strip():
            conftest.write_text(kept.rstrip('\n') + '\n', encoding='utf-8')
        elif kept != content:
            conftest.unlink()           # it held nothing but init's own registration
        return _early_plugin(text)
    if 'flowguard.intent.plugin' not in content:
        conftest.write_text(content.rstrip() + '\n\n' + CONFTEST_PLUGIN['pytest_plugins' in content], encoding='utf-8')
    return text


def _legacy_bindings(cfg):
    """{folder: (files, modules)} of the Python test files that import a flowguard module this version does not
    have (FlowGuard 0.70's bindings import flowguard.map.facts): pytest cannot collect them."""
    import flowguard
    from .deps import NORECURSEDIRS, _patterns, _pytest_options, kept_out, test_scope
    package, scope = Path(flowguard.__file__).parent, test_scope(cfg)
    skipped = _patterns(_pytest_options(cfg), 'norecursedirs', NORECURSEDIRS)
    found = {}
    for folder, names, files in os.walk(cfg.root):
        names[:] = [name for name in names if name not in ('node_modules', '__pycache__')
                    and not kept_out(Path(folder, name).resolve(), skipped)]
        for name in files:
            path = Path(folder) / name
            relative = cfg.rel(path)
            if not name.endswith('.py') or not scope(relative):
                continue
            missing = sorted({module for module in re.findall(r'^\s*(?:from|import)\s+(flowguard(?:\.\w+)+)',
                                                              path.read_text(encoding='utf-8-sig', errors='replace'), re.M)
                              if not (package.joinpath(*module.split('.')[1:]).with_suffix('.py').is_file()
                                      or package.joinpath(*module.split('.')[1:], '__init__.py').is_file())})
            if missing:
                files_, modules = found.setdefault(Path(relative).parent.as_posix(), ([], set()))
                files_.append(relative)
                modules.update(missing)
    return found


def _legacy_binding_lines(cfg, pyproject_text):
    """What init prints about legacy bindings: the folders and the norecursedirs line that keeps pytest out."""
    from .deps import NORECURSEDIRS, _patterns, _pytest_options
    found = _legacy_bindings(cfg)
    if not found:
        return []
    roots = {cfg.rel(cfg.root / value) for value in _patterns(_pytest_options(cfg), 'testpaths', ['.'])}
    folders = sorted({folder.rpartition('/')[2] for folder in found if folder not in roots | {'.'}})
    lines = []
    for folder, (files, modules) in sorted(found.items()):
        lines.append(f'{folder}/ holds {len(files)} test files that import {", ".join(sorted(modules))}, which this '
                     'FlowGuard does not have (bindings of an older FlowGuard): pytest cannot collect them.')
    if folders:
        current = _patterns(_pytest_options(cfg), 'norecursedirs', NORECURSEDIRS)
        where = _pytest_config(cfg.root, pyproject_text) or 'pyproject.toml [tool.pytest.ini_options]'
        wanted = [*current, *(f for f in folders if f not in current)]
        # A TOML file takes a list; pytest.ini, tox.ini and setup.cfg take the patterns separated by spaces.
        value = json.dumps(wanted) if where.partition(' ')[0].endswith('.toml') else ' '.join(wanted)
        lines.append(f'To keep pytest out of them, set in {where} (pytest\'s list plus the folder; a check refuses '
                     f'--ignore): norecursedirs = {value}')
    if len(folders) < len(found):
        lines.append('Files directly in a test root cannot be left out by folder: move or delete them.')
    return lines


# FlowGuard 0.70 wrote its workflow into AGENTS.md (read, map check/confirm, target ..., models); 4.x has none of it.
LEGACY_SECTION = re.compile(r'^##[ \t]+(?P<title>[^\r\n]*?(?:workflow|current-map exception)[^\r\n]*)\r?\n'
                            r'(?P<body>.*?)(?=^#{1,2}[ \t]|^<!-- flowguard:start -->|\Z)', re.M | re.S | re.I)
LEGACY_WORDS = re.compile(r'\b0\.70\.\d+|flowguard (?:read|change)\b|\bmap (?:check|confirm)\b|'
                          r'\btarget (?:start|add|check|promote)\b|flowguard_unit_runner|current[- ]map', re.I)
# A line that still names a command of an earlier FlowGuard, which 4.x does not have. The top-level commands and the
# releases that had them, as the git tags' flowguard/__main__.py gives them (`ERAS`): read, change, map (0.70.2) and
# target (0.70.11) up to 0.75; template and release from 0.70.2 to 1.4; status (0.71.0) and where (0.71.1) to 1.4;
# decide from 0.75 and draft from 1.2, both to 1.4 (4.x drafts with `anchor draft` and `model draft`). The subcommands
# of map and target are 0.70.14's. After a launcher (python, python3.11, py, python.exe) or a backquote any of them is
# a command; written bare, only flowguard read, change, `map SUB` and `target SUB` are, all lowercase: the other
# words are prose after the name ("a FlowGuard release alone", "after each flowguard release", "python -m flowguard
# before each task"). 0.70's `map check` and `map confirm` are read in any case ("Map check must pass"), also in
# prose ("the site map check"), which cannot be told from them. A required version (`requires FlowGuard 0.70.14`,
# `FlowGuard 0.70.x is required`, `flowguard==0.70.14`) and the install tag are 0.70's; a minimum that 4.x meets
# ("requires FlowGuard 0.70.14 or newer") asks for nothing 4.x lacks and is not listed. A launcher may carry the
# interpreter's own options (`py -3.11 -m`, `python -X utf8 -m`, `python3 -I -m`). A capitalized `FlowGuard map` in
# backquotes with no subcommand is the map's name ("the `FlowGuard map` shows the owners"). A line that only names 0.70
# or its files (`.flowguard/models/**`, `flowguard_unit_runner.py` "belong to the earlier 0.70.x workflow") explains
# them and asks for nothing.
ERAS = {**dict.fromkeys(('read', 'change', 'map', 'target'), '0.70–0.75'), 'template': '0.70–1.4', 'release': '0.70–1.4',
        'status': '0.71–1.4', 'where': '0.71–1.4', 'decide': '0.75–1.4', 'draft': '1.2–1.4'}
LAUNCHER = r'\b(?:py|python[\d.]*)(?:\.exe)?\s+(?:-(?!m\b)[\w.]+(?:\s+(?!-)[\w.=]+)?\s+)*'
MAP_SUB = r'(?:scan|discover|show|find|digest|check|lint|impact|deps|confirm|models|verify)\b'
TARGET_SUB = r'(?:start|add|drop|check|promote)\b'
LEGACY_INSTRUCTION = re.compile(
    rf'(?P<command>(?:{LAUNCHER}-m\s+|`)(?i:flowguard)\s+(?:read|change|template|release|status|where|decide|draft'
    rf'|map(?:\s+{MAP_SUB})?|target(?:\s+{TARGET_SUB})?)\b'
    rf'|\bflowguard\s+(?:read|change|map\s+{MAP_SUB}|target\s+{TARGET_SUB})\b|\b(?i:map\s+(?:check|confirm))\b'
    rf'|`target\s+{TARGET_SUB})'
    rf'|(?P<launcher>{LAUNCHER}(?:-m\s+)?(?:[\w.-]+[/\\])*flowguard_unit_runner(?:\.py)?\b)'
    r'|(?P<install>@v0\.70\.\d+)'
    r'|(?P<requirement>\b(?i:requires?|needs?)\s+(?i:flowguard)\s+\**v?0\.70(?:\.\d+|\.x)?(?!\.\d)(?!\w)\**'
    r'(?!\s*(?:\+|(?i:or\s+(?:newer|later|higher|above))))'
    r'|\b(?i:flowguard)\s+\**v?0\.70(?:\.\d+|\.x)?\**\s+(?i:is\s+required)'
    r'|\b(?i:flowguard)(?:\[[\w,-]+\])?\s*[=~]=\s*v?0\.70(?:\.\d+)?)'
    r'|(?P<exception>\b(?i:current[- ]map\s+exception)\b)')


def _era(match):
    """The releases of FlowGuard that had what a `LEGACY_INSTRUCTION` match names: a command's (`ERAS`), else 0.70."""
    if not match['command']:
        return '0.70'
    after = re.search(r'(?i:flowguard)\s+(\w+)', match[0])
    return ERAS[(after[1] if after else match[0].strip('`').split()[0]).lower()]


def _legacy_instructions(content):
    """The lines of the AGENTS.md init writes (`content`, numbered as written) that name an earlier FlowGuard's command,
    launcher, install or required version (`LEGACY_INSTRUCTION`), each named in full with the releases that had it;
    the rules block init wrote is FlowGuard's own and is not read. A ban ("Do not run `flowguard change`") names the
    command too."""
    lines = []
    inside = False
    for number, line in enumerate(content.splitlines(), 1):
        inside = (inside or line.strip() == '<!-- flowguard:start -->') and line.strip() != '<!-- flowguard:end -->'
        if inside or line.strip() == '<!-- flowguard:end -->':
            continue
        eras = {}
        for match in LEGACY_INSTRUCTION.finditer(line):
            if match['command'] and re.fullmatch(r'`FlowGuard\s+map', match[0]):
                continue        # "the `FlowGuard map`": the name of the map, a noun, not 0.70's map command
            eras.setdefault(_era(match), {}).setdefault(match[0].strip('`'), None)
        if eras:
            named = ' and '.join(', '.join(f'`{name}`' for name in names) + f' from FlowGuard {era}' for era, names in eras.items())
            lines.append(f'AGENTS.md:{number} names {named}, which 4.x does not have ({line.strip()[:70]}): reword or delete it')
    return lines


def _legacy_agents(content, rules, newline, languages):
    """(content, lines to print) for an AGENTS.md written for FlowGuard 0.70: its workflow sections ("Six-step
    workflow", the current-map exception) give way to the rules block, in the first one's place; the install
    line and the pinned version (`Use FlowGuard **0.70.14**`) become this version; the project's own rules
    stay byte for byte. A sentence about what 0.70 did is not rewritten to claim it of this version: it is
    kept as it is. `init` lists afterwards, in the file it wrote, each remaining line that still names an earlier
    command (`_legacy_instructions`). A workflow section is FlowGuard's only when its body
    names flowguard, so a project's own release or data workflow stays."""
    removed = []
    def section(match):
        if 'flowguard' not in match['body'].lower() or not LEGACY_WORDS.search(match['body']):
            return match.group(0)
        removed.append(match['title'].strip())
        return '' if len(removed) > 1 or '<!-- flowguard:start -->' in content else rules + newline
    content = LEGACY_SECTION.sub(section, content)
    extra = '[languages]' if languages else ''
    content, installs = re.subn(r'flowguard(?:\[[\w,]+\])? @ (git\+\S+?)@v0\.70\.\d+',
                                lambda match: f'flowguard{extra} @ {match[1]}@v{__version__}', content)
    # Only the pinned statement; any other bold 'FlowGuard **0.70.x**' says what 0.70 was and stays as it is.
    content, versions = re.subn(r'(\bUse\s+FlowGuard\s+\**)0\.70\.\d+', lambda match: match[1] + __version__, content)
    lines = [f'AGENTS.md: the FlowGuard 0.70 section "{title}" is replaced by the project rules block' for title in removed]
    if installs or versions:
        lines.append(f'AGENTS.md: the FlowGuard version and install line now name {__version__}')
    return content, lines


# The CI fragment init writes. A project pytest has tests of runs everything; one whose tests npm runs (TS/JS) runs the
# map checks, which pytest would not, against where its branch left the default branch: a CI checkout is a detached
# HEAD, whose task start is HEAD itself, so without --base it would compare nothing. The base is set on a line of its
# own: GitHub runs a bash step under -e, so a merge-base that fails (no origin/main) fails the step instead of
# giving check an empty --base.
CI_PYTEST = '''# Merge these steps into the project CI after installing FlowGuard.
- uses: actions/checkout@v5
  with:
    fetch-depth: 0
- run: python -m flowguard check --all --deep
'''
CI_STATIC = '''# Merge these steps into the project CI after installing FlowGuard.
# The base is where this branch left the default branch. If the default branch is not called main, replace main below.
- uses: actions/checkout@v5
  with:
    fetch-depth: 0
- run: |
    base=$(git merge-base HEAD "origin/${GITHUB_BASE_REF:-main}")
    python -m flowguard check --static --base "$base"
  shell: bash
'''


def init(cfg):
    pyproject = cfg.root / 'pyproject.toml'
    text = pyproject.read_text(encoding='utf-8') if pyproject.is_file() else ''
    if '[tool.flowguard]' not in text:
        text = text.rstrip() + '\n\n[tool.flowguard]\n'
    sentinel = cfg.root / 'tests/test_flowguard_intent.py'
    if sentinel.exists() and sentinel.read_text(encoding='utf-8') != SENTINEL:
        raise ValueError(f'{sentinel}: an existing test needs merging with the intent sentinel')
    pyproject.write_text(_register_plugin(cfg, sentinel.parent / 'conftest.py', text), encoding='utf-8')
    cfg.intent.mkdir(parents=True, exist_ok=True)
    sentinel.parent.mkdir(parents=True, exist_ok=True)
    sentinel.write_text(SENTINEL, encoding='utf-8')
    from .deps import npm_packages, static_only
    fragment = cfg.root / '.flowguard/ci.yml'
    fragment.parent.mkdir(parents=True, exist_ok=True)
    fragment.write_text(CI_STATIC if static_only(cfg) else CI_PYTEST, encoding='utf-8')
    agents = cfg.root / 'AGENTS.md'
    # Bytes outside the replaced block are kept, including their line endings.
    content = agents.read_bytes().decode('utf-8') if agents.exists() else ''
    newline = '\r\n' if '\r\n' in content else '\n'
    rules = PROJECT_RULES.replace('\n', newline)
    packages = npm_packages(cfg.root)
    content, notes = _legacy_agents(content, rules, newline, bool(packages))
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
    notes += _legacy_instructions(content)
    print('Initialized intent sentinel, pytest plugin, CI fragment and seven project rules.')
    for line in [*notes, *_legacy_binding_lines(cfg, text)]:
        print(line)
    if packages:
        # The generated npm files find this interpreter here; the cache is git-ignored and stays on this machine.
        from flowguard.map.common import cache_dir
        cache_dir(cfg.root)
        (cfg.root / RECORDED_PYTHON).write_text(sys.executable, encoding='utf-8')
    for package in packages:
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
    from .signals import missing_start
    # A recorded task start this repository lacks compares nothing (`cache.task_start`); the check says so first,
    # with the next step, as the title of pytest, `check` and `check --static` does.
    commit, kind = cache.task_baseline(cfg)
    missing = [missing_start(commit)] if kind == 'missing' else []
    result = _ledger_result(cfg, None if missing else commit)
    if not result.present and not result.red:
        print('\n'.join([*missing, f'FlowGuard ledger: no {fallbacks.LEDGER}; python -m flowguard ledger init starts one from the current code.']))
        return 0
    print('\n'.join([*missing, fallbacks.summary(result), *fallbacks.lines(result), *('not checked: ' + line for line in result.grey)]))
    return int(bool(result.red))


def _ledger_result(cfg, baseline):
    """The ledger compared with the current map without running tests (only its deletion when there is none),
    against `baseline` (`owners.baseline`: an explicit `--base`, else the task baseline)."""
    from . import ledger as fallbacks
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
        display(f'if these words set a continuing rule, add it to .flowguard/rules.toml: [rule.<id>] text = "..." '
                f'source = \'{item["id"]} "<exact words>"\'')
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
    if argv and argv[0] in {'status', 'where'}:
        print('this is a FlowGuard 0.7x command; here run python -m flowguard new-task')
        return 0
    from .deprecation import warn as deprecated
    if argv and argv[0] in DEPRECATED_COMMANDS:
        deprecated(argv[0], 'python -m flowguard new-task, check or show NAME')
    parser = argparse.ArgumentParser(prog='flowguard')
    parser.add_argument('--version', action='version', version=__version__)
    commands = parser.add_subparsers(dest='command', metavar='{' + ','.join(COMMANDS) + '}')
    def add_parser(name):
        return commands.add_parser(name, **({'help': COMMANDS[name]} if name in COMMANDS else {}))
    anchor_parser = add_parser('anchor')
    anchor_operations = anchor_parser.add_subparsers(dest='operation', required=True)
    anchor_draft = anchor_operations.add_parser('draft')
    anchor_draft.add_argument('target')
    show_parser = add_parser('show')
    show_parser.add_argument('query', nargs='?')
    show_parser.add_argument('--draft', help=argparse.SUPPRESS)
    show_parser.add_argument('--gaps', help=argparse.SUPPRESS)
    show_parser.add_argument('--full', action='store_true', help='Include decision sites and full candidate metadata')
    show_parser.add_argument('--last', action='store_true', help='Every line of the last run, with its details')
    try_parser = add_parser('try')
    try_parser.add_argument('anchor')
    try_parser.add_argument('inputs', nargs='*')
    try_parser.add_argument('--grid', action='store_true')
    watch_parser = add_parser('watch')
    watch_parser.add_argument('arguments', nargs=argparse.REMAINDER)
    model_parser = add_parser('model')
    model_operations = model_parser.add_subparsers(dest='operation', required=True)
    model_draft = model_operations.add_parser('draft')
    model_draft.add_argument('name')
    check_parser = add_parser('check')
    check_parser.add_argument('--all', action='store_true')
    check_parser.add_argument('--deep', action='store_true', help='Run decision probes and mutation-survival checks')
    check_parser.add_argument('--since', help=argparse.SUPPRESS)
    check_parser.add_argument('--base', type=cache.base_commit,
                              help='Compare behavior with this commit instead of the remembered session baseline')
    check_parser.add_argument('--static', action='store_true',
                              help='Map checks only, without pytest (any language FlowGuard reads, e.g. TS/JS, Prisma, SQL)')
    check_parser.add_argument('--leads', action='store_true',
                              help='Deprecated: every line without the budget; show --last lists them all')
    compare_parser = add_parser('compare')
    compare_parser.add_argument('left')
    compare_parser.add_argument('right')
    add_parser('init')
    add_parser('new-task')
    ledger_parser = add_parser('ledger')
    ledger_operations = ledger_parser.add_subparsers(dest='operation', required=True)
    ledger_operations.add_parser('init', help='Record every existing fallback as legacy')
    ledger_operations.add_parser('check', help='List every difference between the ledger and the code')
    req_parser = add_parser('req')
    operations = req_parser.add_subparsers(dest='operation', required=True)
    add = operations.add_parser('add')
    add.add_argument('file')
    add.add_argument('--id', dest='identifier')
    add.add_argument('--kind', choices=('request', 'glossary', 'adoption'), metavar='request', default='request')
    add.add_argument('--supersedes', action='append', default=[])
    operations.add_parser('list')
    retire = operations.add_parser('retire')
    retire.add_argument('identifier')
    retire.add_argument('--not-owner', action='store_true', required=True)
    retire.add_argument('--note')
    options = parser.parse_args(argv)
    if options.command == 'show' and (options.draft is not None or options.gaps is not None):
        deprecated('show --draft/--gaps', 'python -m flowguard show NAME')
    if options.command == 'check' and options.since is not None:
        deprecated('check --since', 'python -m flowguard check --base REV')
    if options.command == 'req' and options.operation == 'add' and options.kind != 'request':
        deprecated('req --kind ' + options.kind, 'req add FILE --id R<n>')
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
            return show(cfg, options.query, draft=options.draft, gaps=options.gaps, full=options.full, last=options.last)
        if options.command == 'check' and options.static:
            if options.deep or options.since:
                raise ValueError('check --static runs no tests: --deep and --since need the pytest check')
            return static_check(cfg, everything=options.all, base=options.base, leads=options.leads)
        if options.command == 'check':
            return check(cfg, everything=options.all, since=options.since, deep=options.deep, base=options.base,
                         leads=options.leads)
        if options.command == 'init':
            return init(cfg)
        if options.command == 'ledger':
            return ledger(cfg, options.operation)
        if options.command == 'req':
            return requests(cfg, options)
        return screen(cfg, new_task=options.command == 'new-task')
    except BrokenPipeError:
        raise               # The command entry exits quietly when the consumer closes stdout.
    except (ValueError, MapError, OSError) as error:
        print(f'flowguard: {error}', file=sys.stderr)
        return 2
