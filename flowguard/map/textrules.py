"""Computed text/source relationships, never semantic verdicts or a stored registry."""
from __future__ import annotations

import ast
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import re
import shlex

from .common import DEFAULT_IGNORE, matches_any, normalize_newlines, read_source
from .derived import _git, _map, _source, source_names, text_references
from .discover import discover_inventory
from .inventory import build_inventory, list_files, syntax_tree
from .mapfile import ignore_patterns, model_registry, owner_index

_WORDS = re.compile(r"[A-Za-z_][A-Za-z_0-9]*|[\u3400-\u9fff]+")
_NORMATIVE = re.compile(r"\b(?:shall|must|should|never|always|require[sd]?|stop|return|keep|before|after|every|only|priority)\b|必须|不得|不能|应当|优先|禁止", re.I)
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
        if value.strip() and not value.lstrip().startswith('#'):
            if not rows:
                start = line
            rows.append(value)
    if rows:
        yield start, start + len(rows) - 1, '\n'.join(rows)


def _python_text(text):
    """Use the shared syntax owner, retaining physical template spans, not executing strings."""
    tree = syntax_tree(text)
    docstrings, formatted = set(), set()
    functions = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            first = node.body[0] if node.body else None
            if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant):
                docstrings.add(id(first.value))
        if isinstance(node, ast.JoinedStr):
            formatted.update(id(child) for child in ast.walk(node))
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            functions.append(node)
    blocks, literals, programs = [], [], defaultdict(set)
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in docstrings | formatted:
            function = min((fn for fn in functions if fn.lineno <= node.lineno <= fn.end_lineno),
                           key=lambda fn: fn.end_lineno - fn.lineno, default=None)
            if re.fullmatch(r'[A-Za-z_][\w.:-]*', node.value):
                literals.append({'name': node.value, 'line': node.lineno,
                                 'function': function.name if function else None})
            if node.end_lineno > node.lineno or (re.search(r'\s', node.value) and (_NORMATIVE.search(node.value) or '`' in node.value)):
                segment = ast.get_source_segment(text, node) or ''
                match = re.match(r"(?i)^[rub]*(['\"]{3}|['\"])", segment)
                if match and segment.endswith(match[1]):
                    segment = segment[match.end():-len(match[1])]
                    blocks.append((node.lineno, segment))
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == 'ArgumentParser':
            function = min((fn for fn in functions if fn.lineno <= node.lineno <= fn.end_lineno),
                           key=lambda fn: fn.end_lineno - fn.lineno, default=None)
            for keyword in node.keywords:
                if keyword.arg == 'prog' and isinstance(keyword.value, ast.Constant) and isinstance(keyword.value.value, str):
                    programs[function.name if function else '<module>'].add(keyword.value.value)
    return blocks, literals, programs


def _blame(root, path, revision):
    args = ['blame', '--line-porcelain']
    if revision:
        args.append(revision)
    result = _git(root, *args, '--', path)
    if result.returncode:
        return {}
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


def _literal_groups(texts):
    """Maximal exact repeated token runs. A phrase is multiword, never a similarity score."""
    stream, positions, vocabulary, strings = [], [], {}, {}
    by_id = {row['id']: row for row in texts}
    for index, row in enumerate(texts):
        for match in _WORDS.finditer(row['text']):
            word = match[0].casefold()
            token = vocabulary.setdefault(word, len(vocabulary))
            strings[token] = word
            stream.append(token)
            positions.append((row['id'], row['line'] + row['text'][:match.start()].count('\n')))
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
    groups, stack = {}, [(0, 0)]
    for index in range(1, size + 1):
        length, left = common[index], index - 1
        while stack[-1][0] > length:
            count, first = stack.pop()
            left = first
            if count < 2:
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
            groups[key] = {'fragment': phrase, 'token_count': count, 'relation': 'literal occurrence only',
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


def _commands(raw, programs):
    commands = defaultdict(list)
    for path, file in raw['files'].items():
        for entry in file.get('entrypoints', []):
            if entry.get('via') != 'argparse':
                continue
            options = programs.get(path, {}).get(entry.get('parser_symbol'), set())
            if len(options) != 1:
                continue
            try:
                program = ' '.join(shlex.split(next(iter(options))))
            except ValueError:
                continue
            command = program + ' ' + entry['name']
            commands[command].append({'path': path, 'line': entry.get('line'),
                'functions': entry.get('handlers', []), 'unknown': entry.get('handler_unknown', ''),
                'sites': entry.get('handler_sites', [])})
    return commands


def report(root, *, inv=None, raw=None, at=None):
    """Compute complete facts once; callers render the single compact projection by default."""
    original = Path(root).resolve()
    with _source(original, at) as (source, revision):
        data, map_unknown = _map(source)
        unknown = [{'reason': value} for value in map_unknown]
        if at is not None or inv is not None and Path(inv.root).resolve() != source:
            inv = raw = None
        inv = inv or build_inventory(source, ignore_patterns(data), with_bodies=False, write_cache=False, import_roots=data.get('import_roots', ()))
        raw = raw or discover_inventory(source, inv, write_cache=False, data=data)
        unknown.extend({'path': path, 'reason': 'source not parsed: ' + file['parse_error']}
                       for path, file in raw['files'].items() if file.get('parse_error'))
        raw = {**raw, 'files': {path: file for path, file in raw['files'].items() if not file.get('parse_error') and 'module' in file}}
        _, owners = owner_index(data, inv)
        models = model_registry(source, data)
        unknown.extend({'path': issue.path, 'reason': getattr(issue, 'message', str(issue))} for issue in models.issues)
        model_paths = {entry.path for entry in models.entries}
        model_names = {name for entry in models.entries for name in (entry.id, entry.path, Path(entry.path).stem)}
        names = source_names(inv, raw, model_names)
        # A code-analysis ignore such as docs/** must not erase the normative text
        # whose stale references this report is meant to expose. Reuse the shared
        # file listing; do not build a second source inventory or bypass artifacts.
        text_paths = {path for path in list_files(source) if Path(path).suffix.lower() in {'.md', '.rst', '.txt'}
                      and not matches_any(path, DEFAULT_IGNORE)}
        python_paths = set(raw['files']) | model_paths
        texts, references, literals, programs, file_bytes = [], [], [], {}, {}
        for path in sorted(text_paths | python_paths):
            try:
                text = read_source(source / path)
                file_bytes[path] = normalize_newlines((source / path).read_bytes()).splitlines(keepends=True)
                if path in python_paths:
                    blocks, constants, progs = _python_text(text)
                    literals.extend({'path': path, 'kind': 'literal spelling', **row} for row in constants)
                    programs[path] = progs
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
        locations, commands = _locations(inv, raw, literals), _commands(raw, programs)
        command_texts = defaultdict(list)
        refs_by_file = {}
        blame_by_file = {}
        for row in texts:
            path, first, last = row['path'], row['line'], row['end_line']
            if path not in refs_by_file:
                refs_by_file[path] = text_references(source, path, inv, raw, names=names)
                blame_by_file[path] = _blame(original, path, revision if at is not None else None)
            row['provenance'] = _provenance(blame_by_file[path], first, last)
            found = {(ref['line'], ref['name']): dict(ref) for ref in refs_by_file[path] if first <= ref['line'] <= last}
            for offset, line in enumerate(row['text'].splitlines(), first):
                for match in _ORDINARY.finditer(line):
                    value = match[0].rstrip('.:')
                    found.setdefault((offset, value), {'path': path, 'line': offset, 'name': value,
                        'state': 'found in static source' if value in names else 'not found in static source; dynamic binding unknown', 'form': 'ordinary text'})
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
        workflows = [{'command': command, 'state': 'bound',
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
            'workflow_groups': workflows, 'code_literals': literals, 'unknown': unknown}


def _compact(result):
    if result.get('projection') == 'compact':
        return result
    texts = {row['id']: row for row in result['texts']}
    groups = [{key: row[key] for key in ('token_count', 'relation')} | {
        'fragment': row['fragment'][:160], 'count': len(row['occurrences']), 'sources': row['occurrences'][:3]}
        for row in result['literal_groups'][:3]]
    workflows = [{key: row[key] for key in ('command', 'functions', 'relation')} | {
        'count': len(row['sources']), 'sources': [{key: texts[identifier][key] for key in ('path', 'line', 'end_line')} for identifier in row['sources'][:3]]}
        for row in result['workflow_groups'][:3]]
    refs = [{key: row[key] for key in ('path', 'line', 'name', 'state')} for row in result['references'] if 'not found' in row['state']][:3]
    return {key: result[key] for key in ('source', 'revision', 'scope', 'summary')} | {
        'projection': 'compact', 'literal_groups': groups, 'workflow_groups': workflows,
        'references': refs, 'unknown': result['unknown'][:3]}


def render(result, *, as_json=False, full=False):
    """Default human and JSON share one bounded projection; full is explicit fact export."""
    if full:
        return json.dumps(result, ensure_ascii=False, sort_keys=True, indent=None if as_json else 2)
    result = _compact(result)
    if as_json:
        return json.dumps(result, ensure_ascii=False, sort_keys=True)
    summary = result['summary']
    lines = [f"text rules · {result['source']} · report only", f"{summary['texts']} passages in {summary['source_files']} files; {summary['literal_groups']} literal groups; {summary['unresolved_references']} unresolved references; {summary['workflow_groups']} attributed workflows; {summary['unplaced']} unplaced"]
    for row in result['literal_groups']:
        lines.append('shared literal ' + repr(row['fragment']) + ' · ' + str(row['count']) + ' passages · ' + ', '.join(item['path'] + ':' + str(item['line']) for item in row['sources']))
    for row in result['references']:
        lines.append(row['path'] + ':' + str(row['line']) + ' ' + row['name'] + ' · ' + row['state'])
    for row in result['workflow_groups']:
        lines.append(row['command'] + ' → ' + ', '.join(row['functions']) + ' · ' + str(row['count']) + ' original passages')
    lines.extend('unknown: ' + row['reason'] for row in result['unknown'])
    return '\n'.join(lines)
