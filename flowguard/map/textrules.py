"""Computed text/source relationships, never semantic verdicts or a stored registry."""
from __future__ import annotations

from collections import defaultdict
import hashlib
import json
from pathlib import Path
import re
import shlex

from .common import DEFAULT_IGNORE, git_common_directory, git_head, git_run, matches_any, normalize_newlines, read_source
from .derived import _map, _source, _writes_cache, bound as bound_rows, omitted_line, source_names, text_reference_hint, text_references
from .discover import NORMATIVE as _NORMATIVE, discover_inventory, python_text
from .inventory import build_inventory, list_files, syntax_tree
from .mapfile import ignore_patterns, model_registry, owner_index

_WORDS = re.compile(r"[A-Za-z_][A-Za-z_0-9]*|[\u3400-\u9fff]+")
_ORDINARY = re.compile(r"\b[A-Za-z_][\w]*(?:_[\w]+|[.:/#-][\w./:#-]+)\b")
_BLOCK = re.compile(r"^\s*(?:[-*+]\s+|\d+[.)]\s+|\|)")


def _hash(value):
    return hashlib.sha256(value).hexdigest()


def _paragraphs(text, base=1):
    """Keep physical source lines; lists have separate passages, fences are examples."""
    rows, start, fenced = [], base, False
    for line, value in enumerate(text.splitlines(), base):
        boundary = not value.strip() or value.lstrip().startswith('#') or bool(_BLOCK.match(value))
        if value.lstrip().startswith(('```', '~~~')):
            if rows:
                yield start, line - 1, '\n'.join(rows)
                rows = []
            fenced = not fenced
            continue
        if fenced:
            continue
        if boundary and rows:
            yield start, line - 1, '\n'.join(rows)
            rows = []
        if value.lstrip().startswith('#'):
            if '`' in value:
                yield line, line, value
            continue
        if value.strip():
            if not rows:
                start = line
            rows.append(value)
    if rows:
        yield start, start + len(rows) - 1, '\n'.join(rows)


def _blame(root, path, revision, contents):
    """Origins of exactly the bytes the facts were read from: the revision's file, or the bytes read from the working tree.

    No origin outside Git, before the first commit or for a file that commit does not hold; a failing Git raises."""
    if git_common_directory(root) is None:
        return {}
    commit = revision or git_head(root)
    if commit is None or git_run(root, 'rev-parse', '-q', '--verify', f'{commit}:./{path}', allowed=(0, 1)).returncode:
        return {}  # exit 1: the commit does not hold this file
    args = ['blame', '--line-porcelain', *([revision] if revision else ['--contents', '-']), '--', path]
    result = git_run(root, *args, input=None if revision else contents)
    found, current, original, commit, source = {}, None, None, None, path
    for row in result.stdout.decode('utf-8', errors='replace').splitlines():
        header = re.fullmatch(r'([0-9a-f]{40,64}) (\d+) (\d+)(?: \d+)?', row)
        if header:
            commit, original, current = header[1], int(header[2]), int(header[3])
        elif row.startswith('filename '):
            source = row[9:]
        elif row.startswith('\t') and current is not None:
            found[current] = {'revision': commit, 'path': source, 'line': original} if commit and set(commit) != {'0'} else None
    return found


def _provenance(blame, first, last):
    rows, missing = [], False
    for line in range(first, last + 1):
        value = blame.get(line)
        if value is None:
            missing = True
            continue
        if value not in rows:
            rows.append(value)
    return {'state': 'partial' if rows and missing else 'git' if rows else 'unknown',
            'origins': rows, **({'reason': 'some source lines have no committed Git origin'} if missing else {})}


def _origin(row):
    """Compact origin: consecutive lines of one commit and path as one span, e.g. git e2664de144b9 3-8."""
    provenance, spans = row['provenance'], []
    for origin in provenance['origins']:
        last = spans[-1] if spans else None
        if last and last[:2] == (origin['revision'], origin['path']) and last[3] + 1 == origin['line']:
            spans[-1] = (*last[:3], origin['line'])
        else:
            spans.append((origin['revision'], origin['path'], origin['line'], origin['line']))
    text = ', '.join('git ' + revision[:12] + ' ' + ('' if path == row['path'] else path + ':') + f'{first}-{last}'
                     for revision, path, first, last in spans)
    return {'git': text, 'partial': text + '; some lines are not committed'}.get(provenance['state'], 'origin unknown: no committed Git origin')


def _literal_groups(texts):
    """Maximal exact repeated token runs. A phrase is multiword, never a similarity score."""
    stream, positions, vocabulary, strings = [], [], {}, {}
    by_id = {row['id']: row for row in texts}
    for index, row in enumerate(texts):
        line, cursor = row['line'], 0
        for match in _WORDS.finditer(row['text']):
            line += row['text'][cursor:match.start()].count('\n')
            cursor = match.end()
            word = match[0].casefold()
            token = vocabulary.setdefault(word, len(vocabulary))
            strings[token] = word
            stream.append(token)
            positions.append((row['id'], line))
        stream.append(-index - 1)  # Different boundaries cannot share a cross-passage match.
        positions.append(None)
    size = len(stream)
    if size < 2:
        return []
    suffixes, ranks, width = list(range(size)), stream[:], 1
    while width < size:
        suffixes.sort(key=lambda pos: (ranks[pos], ranks[pos + width] if pos + width < size else -size - 1))
        updated, rank = [0] * size, 0
        for offset, pos in enumerate(suffixes):
            if offset:
                previous = suffixes[offset - 1]
                rank += (ranks[pos], ranks[pos + width] if pos + width < size else -size - 1) != (ranks[previous], ranks[previous + width] if previous + width < size else -size - 1)
            updated[pos] = rank
        ranks = updated
        if rank == size - 1:
            break
        width *= 2
    order = [0] * size
    for index, pos in enumerate(suffixes):
        order[pos] = index
    common, matched = [0] * (size + 1), 0
    for pos in range(size):
        index = order[pos]
        if not index:
            matched = 0
            continue
        other = suffixes[index - 1]
        while pos + matched < size and other + matched < size and stream[pos + matched] == stream[other + matched]:
            matched += 1
        common[index] = matched
        matched = max(0, matched - 1)
    # A right-maximal LCP interval is redundant if every actual occurrence has
    # the same ordinary predecessor. Check before collapsing repeated passages.
    predecessors, left_runs = [], []
    for index, pos in enumerate(suffixes):
        previous = stream[pos - 1] if pos and positions[pos - 1] is not None else -pos - 1
        predecessors.append(previous)
        left_runs.append(left_runs[-1] if index and previous == predecessors[index - 1] else index)
    groups, stack = {}, [(0, 0)]
    for index in range(1, size + 1):
        length, left = common[index], index - 1
        while stack[-1][0] > length:
            count, first = stack.pop()
            left = first
            if count < 2:
                continue
            if predecessors[first] >= 0 and left_runs[index - 1] <= first:
                continue
            occurrence = {}
            for pos in suffixes[first:index]:
                if positions[pos] is not None:
                    identifier, line = positions[pos]
                    occurrence.setdefault(identifier, {'source': identifier, 'path': by_id[identifier]['path'],
                        'line': line, 'end_line': positions[pos + count - 1][1]})
            if len(occurrence) < 2:
                continue
            phrase = ' '.join(strings[token] for token in stream[suffixes[first]:suffixes[first] + count])
            key = phrase, tuple(sorted(occurrence))
            identifier = _hash(json.dumps(key, ensure_ascii=False).encode())[:20]
            groups[key] = {'id': identifier, 'fragment': phrase, 'token_count': count, 'relation': 'literal occurrence only',
                           'occurrences': sorted(occurrence.values(), key=lambda row: (row['path'], row['line']))}
        if stack[-1][0] < length:
            stack.append((length, left))
    return sorted(groups.values(), key=lambda row: (-row['token_count'], -len(row['occurrences']), row['fragment']))


def _locations(inv, raw, literals):
    found = defaultdict(list)
    for path in inv.files:
        found[path].append({'path': path, 'kind': 'file'})
    for path, file in raw['files'].items():
        for symbol, fn in file.get('functions', {}).items():
            row = {'path': path, 'line': fn['line'], 'function': symbol, 'kind': 'function'}
            for name in (symbol, symbol.rsplit('.', 1)[-1], path + '#' + symbol, path + ':' + symbol, file['module'] + '.' + symbol):
                if row not in found[name]:
                    found[name].append(row)
    for row in literals:
        found[row['name']].append({key: value for key, value in row.items() if key != 'name'})
    return found


def _placement(path, owners, functions=(), evidence=()):
    choices = owners.get(path, [])
    state = 'bound' if functions or len(choices) == 1 else 'unknown'
    return {'state': state, 'owners': choices, 'functions': sorted(set(functions)), 'evidence': list(evidence),
            **({'reason': 'no unique owner or explicit function/command binding'} if state == 'unknown' else {})}


def _commands(raw, programs, unknown):
    commands = defaultdict(list)
    for path, file in raw['files'].items():
        for entry in file.get('entrypoints', []):
            if entry.get('via') != 'argparse':
                continue
            options = programs.get(path, {}).get(entry.get('parser_symbol'), set())
            if len(options) != 1:
                continue
            prog = next(iter(options))
            try:
                program = ' '.join(shlex.split(prog))
            except ValueError as error:
                unknown.append({'path': path, 'line': entry.get('line'), 'command': entry['name'],
                                'reason': f'argparse prog {prog!r} cannot be split into words: {error}'})
                continue
            command = program + ' ' + entry['name']
            commands[command].append({'path': path, 'line': entry.get('line'),
                'functions': entry.get('handlers', []), 'unknown': entry.get('handler_unknown', ''),
                'sites': entry.get('handler_sites', [])})
    return commands


def report(root, *, inv=None, raw=None, at=None):
    """Compute complete facts once; callers render the single compact projection by default."""
    original = Path(root).resolve()
    cache = _writes_cache(original, at)
    with _source(original, at) as (source, revision):
        data, unknown = _map(source), []
        if at is not None or inv is not None and Path(inv.root).resolve() != source:
            inv = raw = None
        inv = inv or build_inventory(source, ignore_patterns(data), with_bodies=False, write_cache=cache, import_roots=data.get('import_roots', ()))
        raw = raw or discover_inventory(source, inv, write_cache=cache, data=data)
        unknown.extend({'path': path, 'reason': 'source not parsed: ' + file['parse_error']}
                       for path, file in raw['files'].items() if file.get('parse_error'))
        raw = {**raw, 'files': {path: file for path, file in raw['files'].items() if not file.get('parse_error') and 'module' in file}}
        _, owners = owner_index(data, inv)
        models = model_registry(source, data)
        unknown.extend({'path': issue.path, 'reason': getattr(issue, 'message', str(issue))} for issue in models.issues)
        model_paths = {entry.path for entry in models.entries}
        model_names = {name for entry in models.entries for name in (entry.id, entry.path, Path(entry.path).stem)}
        names = source_names(inv, raw, model_names)
        basenames = defaultdict(list)
        for path in inv.files:
            basenames[Path(path).name].append(path)
        # A code-analysis ignore such as docs/** must not erase the normative text
        # whose stale references this report is meant to expose. Reuse the shared
        # file listing; do not build a second source inventory or bypass artifacts.
        text_paths = {path for path in list_files(source) if Path(path).suffix.lower() in {'.md', '.rst', '.txt'}
                      and not matches_any(path, DEFAULT_IGNORE)}
        python_paths = set(raw['files']) | model_paths
        texts, references, literals, programs, file_bytes, contents = [], [], [], {}, {}, {}
        for path in sorted(text_paths | python_paths):
            try:
                contents[path] = (source / path).read_bytes()
                text = read_source(source / path, data=contents[path])
                file_bytes[path] = normalize_newlines(contents[path]).splitlines(keepends=True)
                if path in python_paths:
                    # Discovery's per-file facts carry these for its sources; model files are read here.
                    facts = raw['files'][path]['python_text'] if path in raw['files'] else python_text(text, syntax_tree(text))
                    literals.extend({'path': path, 'kind': 'literal spelling', **row} for row in facts['literals'])
                    programs[path] = facts['programs']
                    blocks = facts['blocks']
                else:
                    blocks = [(1, text)]
            except (OSError, ValueError, SyntaxError) as exc:
                unknown.append({'path': path, 'reason': str(exc)})
                continue
            for base, block in blocks:
                for first, last, passage in _paragraphs(block, base):
                    if not (_NORMATIVE.search(passage) or '`' in passage or _ORDINARY.search(passage)):
                        continue
                    fingerprint = _hash(b''.join(file_bytes[path][first - 1:last]))
                    identifier = _hash((path + ':' + str(first) + ':' + fingerprint).encode())[:20]
                    texts.append({'id': identifier, 'path': path, 'line': first, 'end_line': last, 'text': passage,
                        'fingerprint': fingerprint, 'placement': _placement(path, owners)})
        locations, commands = _locations(inv, raw, literals), _commands(raw, programs, unknown)
        command_texts = defaultdict(list)
        refs_by_file = {}
        for row in texts:
            path, first, last = row['path'], row['line'], row['end_line']
            if path not in refs_by_file:
                refs_by_file[path] = text_references(source, path, inv, raw, names=names)
            found = {(ref['line'], ref['name']): dict(ref) for ref in refs_by_file[path] if first <= ref['line'] <= last}
            for offset, line in enumerate(row['text'].splitlines(), first):
                for match in _ORDINARY.finditer(line):
                    value = match[0].rstrip('.:')
                    found.setdefault((offset, value), {'path': path, 'line': offset, 'name': value,
                        **text_reference_hint(source, path, value, names, basenames=basenames), 'form': 'ordinary text'})
            functions, evidence = set(), []
            for command, bindings in commands.items():
                if not re.search(r'(?<![\w-])' + re.escape(command) + r'(?![\w-])', row['text']):
                    continue
                handlers = {tuple(binding['functions']) for binding in bindings if not binding['unknown']}
                if len(handlers) == 1 and next(iter(handlers)) and all(not binding['unknown'] for binding in bindings):
                    actual = list(next(iter(handlers)))
                    functions.update(actual)
                    evidence.append({'kind': 'complete command', 'command': command, 'bindings': bindings})
                    command_texts[command].append(row['id'])
                else:
                    unknown.append({'path': path, 'line': first, 'command': command, 'reason': 'command handler binding is unknown or ambiguous'})
            for ref in found.values():
                matches = locations.get(ref['name'], [])
                if ref.get('kind') == 'file candidate':
                    matches = [{'path': file, 'kind': 'file candidate'} for file in ref['files']]
                explicit = [value for value in matches if value.get('function') and ref['name'] in {
                    value['path'] + '#' + value['function'], value['path'] + ':' + value['function'],
                    raw['files'].get(value['path'], {}).get('module', '') + '.' + value['function']}]
                bound = [value['path'] + '#' + value['function'] for value in explicit]
                if len(set(bound)) == 1:
                    functions.update(bound)
                placement = _placement(path, {}, bound if len(set(bound)) == 1 else (),
                    [{'kind': 'explicit source reference', 'name': ref['name']}] if len(set(bound)) == 1 else ())
                references.append({**ref, 'source': row['id'], 'locations': matches, 'placement': placement})
            row['placement'] = _placement(path, owners, functions, evidence)
        workflows = [{'id': _hash(json.dumps(['workflow', command, sorted(set(identifiers))]).encode())[:20],
            'command': command, 'state': 'bound',
            'functions': sorted({fn for binding in commands[command] for fn in binding['functions']}),
            'sources': sorted(set(identifiers)), 'evidence': commands[command], 'relation': 'attributed original text only'}
            for command, identifiers in sorted(command_texts.items()) if len(set(identifiers)) > 1]
        groups = _literal_groups(texts)
        summary = {'texts': len(texts), 'source_files': len({row['path'] for row in texts}), 'references': len(references),
            'unresolved_references': sum('not found' in row['state'] for row in references),
            'literal_groups': len(groups), 'workflow_groups': len(workflows),
            'unplaced': sum(row['placement']['state'] == 'unknown' for row in texts), 'code_literals': len(literals), 'unknown': len(unknown)}
        return {'projection': 'full', 'root': str(original), 'source': str(at) if at is not None else 'working tree',
            'revision': revision, 'scope': 'computed text/source facts; shared literals do not prove equivalent obligations; spelling existence does not prove owner binding; no semantic conflict or check verdict',
            'summary': summary, 'texts': texts, 'references': references, 'literal_groups': groups,
            'workflow_groups': workflows, 'code_literals': literals, 'unknown': unknown,
            # A later selection blames exactly these bytes, not a working tree edited since.
            'blame_source': {'revision': revision if at is not None else None,
                             'contents': {path: contents[path] for path in {row['path'] for row in texts}}}}


def select(result, selector, *, origins=False):
    """Select full originals in relevance order; text: uses a case-insensitive literal substring, not semantics.

    Passages printed with their text get their Git origin: source: and group: selections, and
    every selected passage with ``origins``; other selections list passages without blaming a file.
    """
    if result.get('projection') != 'full':
        raise ValueError('text selection requires full facts, not a compact projection')
    texts = {row['id']: row for row in result['texts']}
    group, kind, phrase = None, 'file', None
    if selector.startswith('source:'):
        kind = 'source'
        identifiers = {selector[7:]} & texts.keys()
    elif selector.startswith('group:'):
        kind = 'group'
        group = next((row for row in result['literal_groups'] + result['workflow_groups']
                      if row['id'] == selector[6:]), None)
        identifiers = set(group.get('sources', ())) if group and 'sources' in group else {
            hit['source'] for hit in group['occurrences']} if group else set()
    elif selector.startswith('text:'):
        kind, phrase = 'literal', selector[5:].casefold()
        if not phrase:
            raise ValueError('text: requires a nonempty literal substring')
        identifiers = {row['id'] for row in result['texts'] if phrase in row['text'].casefold()}
    else:
        path = Path(selector)
        if path.is_absolute() or '..' in path.parts:
            raise ValueError('text selector must use a relative file, source:<id>, group:<id> or text:<literal phrase>')
        identifiers = {row['id'] for row in result['texts'] if row['path'] == path.as_posix()}
    if not identifiers:
        raise ValueError('no recorded original passages for text selector: ' + selector)
    related = []
    if kind != 'group':
        for row in result['literal_groups'] + result['workflow_groups']:
            sources = set(row['sources']) if 'sources' in row else {hit['source'] for hit in row['occurrences']}
            if sources & identifiers and (phrase is None or phrase in row.get('fragment', row.get('command', '')).casefold()):
                related.append({'id': row['id'], 'selector': 'group:' + row['id'], 'count': len(sources),
                                **({'command': row['command']} if 'command' in row else {'fragment': row['fragment'][:160]})})
    unresolved = {row['source'] for row in result['references'] if 'not found' in row['state']}
    shared = {hit['source'] for row in result['literal_groups'] for hit in row['occurrences']}
    shared.update(identifier for row in result['workflow_groups'] for identifier in row['sources'])
    chosen = sorted((row for row in result['texts'] if row['id'] in identifiers),
                    key=lambda row: (row['id'] not in unresolved, row['id'] not in shared, row['path'], row['line']))
    if origins or kind in {'source', 'group'}:
        blamed, source = {}, result['blame_source']
        for path in dict.fromkeys(row['path'] for row in chosen):
            blamed[path] = _blame(result['root'], path, source['revision'], source['contents'][path])
        chosen = [{**row, 'provenance': _provenance(blamed[row['path']], row['line'], row['end_line'])} for row in chosen]
    return {key: result[key] for key in ('source', 'revision', 'scope')} | {
        'projection': 'selected', 'selection': {'selector': selector, 'kind': kind},
        'texts': chosen,
        'references': sorted((row for row in result['references'] if row['source'] in identifiers),
                             key=lambda row: ('not found' not in row['state'], row['path'], row['line'])),
        'literal_groups': [group] if group and 'occurrences' in group else [],
        'workflow_groups': [group] if group and 'sources' in group else [],
        'related_groups': related,
        'unknown': [row for row in result['unknown'] if 'path' not in row or
                    row['path'] in {texts[identifier]['path'] for identifier in identifiers}]}


def _compact(result):
    if result.get('projection') == 'compact':
        return result
    texts = {row['id']: row for row in result['texts']}
    groups = [{key: row[key] for key in ('id', 'token_count', 'relation')} | {
        'selector': 'group:' + row['id'],
        'fragment': row['fragment'][:160], 'count': len(row['occurrences']), 'sources': row['occurrences']}
        for row in result['literal_groups']]
    workflows = [{key: row[key] for key in ('id', 'command', 'functions', 'relation')} | {
        'selector': 'group:' + row['id'],
        'count': len(row['sources']), 'sources': [{key: texts[identifier][key] for key in ('id', 'path', 'line', 'end_line')} for identifier in row['sources']]}
        for row in result['workflow_groups']]
    refs = [{key: row[key] for key in ('source', 'path', 'line', 'name', 'state')} for row in result['references'] if 'not found' in row['state']]
    return {key: result[key] for key in ('source', 'revision', 'scope', 'summary')} | {
        'projection': 'compact', 'literal_groups': groups, 'workflow_groups': workflows,
        'references': refs, 'unknown': result['unknown'], 'selectors': ['FILE', 'source:<id>', 'group:<id>']}


_SELECTED = (('texts', 'passages'), ('related_groups', 'related groups'), ('references', 'references'), ('unknown', 'unknown'))
_SUMMARY = (('literal_groups', 'literal groups'), ('references', 'unresolved references'), ('workflow_groups', 'workflows'), ('unknown', 'unknown'))


def project(result, *, all_rows=False):
    """The one projection human and JSON output print, bounded unless all_rows; projecting twice changes nothing."""
    result = result if result.get('projection') == 'selected' else _compact(result)
    omitted, keep = dict(result.get('omitted', {})), dict(all_rows=all_rows)
    shown = {**result, **{key: bound_rows(result[key], label, omitted, **keep)
                          for key, label in (_SELECTED if result['projection'] == 'selected' else _SUMMARY)}}
    if result['projection'] == 'selected':
        shown['references'] = [{key: row[key] for key in ('source', 'path', 'line', 'name', 'state')} for row in shown['references']]
    else:
        # A group's count states how many passages share it; its listed locations are bounded alike.
        for key in ('literal_groups', 'workflow_groups'):
            shown[key] = [{**row, 'sources': bound_rows(row['sources'], 'sources', {}, **keep)} for row in shown[key]]
    if not all_rows:
        shown['omitted'] = omitted
    return shown


def _unknown(row):
    place = row['path'] + (':' + str(row['line']) if 'line' in row else '') if 'path' in row else ''
    return 'unknown: ' + ' · '.join(part for part in (place, row.get('command'), row['reason']) if part)


def _excerpt(text, width=100):
    flat = ' '.join(text.split())
    return flat if len(flat) <= width else flat[:width] + '…'


def render(result, *, as_json=False, full=False, all_rows=False):
    """Default human and JSON share one bounded projection; full is explicit fact export."""
    if full:
        facts = {key: value for key, value in result.items() if key != 'blame_source'}
        return json.dumps(facts, ensure_ascii=False, sort_keys=True, indent=None if as_json else 2)
    result = project(result, all_rows=all_rows)
    if as_json:
        return json.dumps(result, ensure_ascii=False, sort_keys=True)
    if result['projection'] == 'selected':
        lines = [f"text rules · {result['source']} · {result['selection']['selector']} · original passages"]
        for row in result['texts']:
            head = f"{row['path']}:{row['line']}-{row['end_line']} · source:{row['id']}"
            lines.extend([head + ' · ' + _origin(row), row['text']] if 'provenance' in row else [head + ' · ' + _excerpt(row['text'])])
        for row in result['related_groups']:
            label = row['command'] if 'command' in row else 'shared literal ' + repr(row['fragment'])
            lines.append(row['selector'] + ' · ' + label + ' · ' + str(row['count']) + ' original passages')
        for row in result['references']:
            lines.append(row['path'] + ':' + str(row['line']) + ' ' + row['name'] + ' · ' + row['state'])
        if (line := omitted_line(result.get('omitted'), 'passages with unresolved references, then shared literals, then file order')):
            lines.append(line + '; text:<literal phrase> narrows original passages and group hints')
        lines.extend(_unknown(row) for row in result['unknown'])
        return '\n'.join(lines)
    summary = result['summary']
    lines = [f"text rules · {result['source']} · report only", f"{summary['texts']} passages in {summary['source_files']} files; {summary['literal_groups']} literal groups; {summary['unresolved_references']} unresolved references; {summary['workflow_groups']} attributed workflows; {summary['unplaced']} unplaced"]
    for row in result['literal_groups']:
        lines.append(row['selector'] + ' · shared literal ' + repr(row['fragment']) + ' · ' + str(row['count']) + ' passages · ' + ', '.join(item['path'] + ':' + str(item['line']) for item in row['sources']))
    for row in result['references']:
        lines.append(row['path'] + ':' + str(row['line']) + ' ' + row['name'] + ' · ' + row['state'])
    for row in result['workflow_groups']:
        lines.append(row['selector'] + ' · ' + row['command'] + ' → ' + ', '.join(row['functions']) + ' · ' + str(row['count']) + ' original passages')
    hint = 'select FILE, source:<id> or group:<id> for original passages'
    line = omitted_line(result.get('omitted'), 'literal groups by length')
    lines.append(line + '; ' + hint if line else hint)
    lines.extend(_unknown(row) for row in result['unknown'])
    return '\n'.join(lines)
