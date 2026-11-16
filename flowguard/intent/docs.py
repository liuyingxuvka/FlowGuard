"""Documents tied to code (design 4.4; R91, R92): a Markdown text that describes code says so with one comment,

    <!-- flowguard: about backend/src/services/allocation.service.ts:allocationService.create -->

and the text from it to the next marker or heading (or, when a heading follows the marker, that heading's section)
describes that site, read as a known.toml site is (`sources.site_resolver`: a function, method, object.method,
constant or Model.field of a file, or a file's path alone). When a change edits the site and not that text, the
block says so with an `impact` line, never a red one: the text may now be out of date, and only a reader can tell.
A marker this change writes with a site that names nothing is red; one that an earlier change left so, or whose site
this change removed, is an `impact` line when this change touches it, and `check --all` lists every one.

A list the code already holds is generated instead: the lines between `<!-- flowguard: generate KIND ARG -->` and
`<!-- flowguard: end -->` are written from the map by `python -m flowguard docs` (`rewrite`), and a run whose region
differs from what the map gives now names it with an `impact` line."""
from __future__ import annotations

import os
import re

from flowguard.map.common import git_run, read_source

MARKER = re.compile(r'<!--\s*flowguard:\s*about\s+(\S+?)\s*-->')
HEADING = re.compile(r'(#{1,6})\s')
REVIEW = 'reread that text and correct it if it no longer holds'


def documents(root):
    """The Markdown files of the repository, tracked or not (Git's ignore rules apply), that hold a marker."""
    listed = git_run(root, 'ls-files', '-z', '--cached', '--others', '--exclude-standard', '--', '*.md').stdout
    found = []
    for name in sorted({os.fsdecode(item) for item in listed.split(b'\0') if item}):
        path = root / name
        if path.is_file() and b'flowguard:' in path.read_bytes():
            found.append(name)
    return found


def markers(text):
    """[(site, line, span)] of the `about` markers of a document's text: `span` is the text the marker describes, the
    lines after it to the next marker or heading; when a heading follows the marker, that heading's section, to the
    next heading of its level or above."""
    lines = text.splitlines()
    found = []
    for index, line in enumerate(lines):
        match = MARKER.search(line)
        if not match:
            continue
        start = index + 1
        while start < len(lines) and not lines[start].strip():
            start += 1
        heading = HEADING.match(lines[start]) if start < len(lines) else None
        end = start + 1 if heading else start
        while end < len(lines) and not MARKER.search(lines[end]):
            other = HEADING.match(lines[end])
            if other and (not heading or len(other[1]) <= len(heading[1])):
                break
            end += 1
        found.append((match[1], index + 1, '\n'.join(lines[start:end]).strip()))
    return found


def findings(change, touched, *, everything=False):
    """The document findings for `owners.static_findings`: an `impact` line per `about` marker whose site this change
    edits (its node is in `touched`, or `Change.edited` sees a comment inside it) while the text it describes stays as
    it was, and per marker whose site names nothing that this change touches; a red input finding per marker this
    change adds or edits whose site names nothing. Without a baseline nothing is compared."""
    from .owners import Findings
    from .signals import Line
    from .sources import _input, site_resolver
    found = Findings()
    if not change.baseline:
        return found
    graph, resolve = change.graph, None
    for document in documents(graph.root):
        then = change.old_text(document)
        before = {(site, span) for site, _, span in markers(then)} if then is not None else set()
        sites_then = {site for site, _ in before}
        for site, line, span in markers(read_source(graph.root / document)):
            path = site.rpartition(':')[0] or site
            if ':' not in site:             # a file's path alone: the text describes the whole file
                nodes, files = set(), {site}
                problem = '' if (graph.root / site).is_file() else f'site {site}: no such file in this repository'
            else:
                if resolve is None:
                    resolve = site_resolver(graph, change)
                nodes, files, problem = resolve(site)
            place = f'{document}:{line}'
            if problem:
                if site not in sites_then:          # this change wrote the marker
                    found.issues.append(_input(f'docs:{place}', f'about {site}', place, [problem],
                                               f'name one function, constant or Model.field, or a file, in the marker at {place}',
                                               [document]))
                elif everything or path in change.baseline_paths():
                    found.lines.append(Line('impact', f'docs:{place}', '', f'{place} describes {site}, which names nothing now',
                                            'update that text and its marker, or remove them', (place,), (problem,)))
                continue
            edited = bool(nodes & touched) or bool(files & change.files)
            if edited and (site, span) in before:
                found.lines.append(Line('impact', f'docs:{place}', '', f'{place} describes {site}, which this change edits',
                                        REVIEW, (place,), ()))
        regions_then = {(kind, argument) for kind, argument, *_ in regions(then)} if then is not None else set()
        for line, kind, argument, problem in stale(graph, document, read_source(graph.root / document)):
            place = f'{document}:{line}'
            if problem and (kind, argument) not in regions_then:      # this change wrote the region
                found.issues.append(_input(f'docs:{place}', f'generate {kind} {argument}', place, [problem],
                                           f'correct the marker at {place}', [document]))
            elif problem:
                found.lines.append(Line('impact', f'docs:{place}', '', f'{place} generate {kind} {argument} cannot be written',
                                        'correct its marker or remove the region', (place,), (problem,)))
            else:
                found.lines.append(Line('impact', f'docs:{place}', '', f'{place} generate {kind} {argument} is out of date',
                                        'python -m flowguard docs rewrites it', (place,), ()))
    return found


# ---- generated regions --------------------------------------------------------------------------------------------
# `<!-- flowguard: generate KIND ARG -->` ... `<!-- flowguard: end -->`: the lines between are FlowGuard's, written
# from the map by `python -m flowguard docs`. They carry no line numbers, which an edit above would date.

GENERATE = re.compile(r'<!--\s*flowguard:\s*generate\s+(\S+)\s+(\S+?)\s*-->')
END = re.compile(r'<!--\s*flowguard:\s*end\s*-->')
KINDS = ('fields', 'values', 'functions', 'constants')


def regions(text):
    """[(kind, argument, line, start, end, body)] of a document's generated regions: `line` is the marker's line
    (1-based), the body the lines from `start` to `end` (0-based, `end` the end marker's index, or None when the
    region has no end marker)."""
    lines = text.splitlines()
    found = []
    for index, line in enumerate(lines):
        match = GENERATE.search(line)
        if match:
            end = next((other for other in range(index + 1, len(lines)) if END.search(lines[other])
                        or GENERATE.search(lines[other])), None)
            if end is not None and not END.search(lines[end]):
                end = None
            found.append((match[1], match[2], index + 1, index + 1, end,
                          '\n'.join(lines[index + 1:end]).strip('\n') if end is not None else ''))
    return found


def _cell(text):
    return str(text).replace('|', '\\|').replace('\n', ' ').strip()


def generated(graph, kind, argument):
    """(the Markdown of one region, '') or ('', what is wrong): `fields Model` a table of a Prisma model's fields with
    each schema file's type where they differ, `values NAME` the members of the value set declared under that name,
    `functions path` and `constants path` the functions with their signatures and the module-level literal
    constants with their values of one file."""
    import json
    if kind not in KINDS:
        return '', f'generate {kind}: the kinds are {", ".join(KINDS)}'
    if kind == 'fields':
        found = [(schema['file'], item) for schema in graph.schemas() if schema['kind'] == 'prisma'
                 for item in schema.get('models', ()) if item['name'] == argument]
        if not found:
            return '', f'generate fields {argument}: no Prisma model {argument}'
        order, types, columns = [], {}, {}
        for file, item in sorted(found, key=lambda pair: pair[0]):
            for column in item.get('fields', ()):
                name = column['name']
                if name not in types:
                    order.append(name)
                text = column['type'] + ('[]' if column.get('list') else '') + ('?' if column.get('optional') else '')
                types.setdefault(name, {}).setdefault(text, []).append(file)
                columns.setdefault(name, column.get('column') or name)
        every = {file for file, _ in found}
        def typed(name):
            if len(types[name]) == 1 and set(next(iter(types[name].values()))) == every:
                return next(iter(types[name]))
            return ', '.join(f'{text} ({", ".join(files)})' for text, files in types[name].items())
        rows = [f'| {_cell(name)} | {_cell(typed(name))} | {_cell(columns[name])} |' for name in order]
        return '\n'.join(['| Field | Type | Column |', '|---|---|---|', *rows]), ''
    if kind == 'values':
        sets = {tuple(item['values']) for item in graph.declarations(exported=False) if item['name'] == argument} \
            or {tuple(item['values']) for item in graph.value_sets() if item['name'] == argument}
        if len(sets) != 1:
            return '', f'generate values {argument}: ' + (f'{len(sets)} different value sets have that name' if sets else 'no value set of that name')
        return '\n'.join(f'- `{value}`' for value in next(iter(sets))), ''
    if not (graph.root / argument).is_file():
        return '', f'generate {kind} {argument}: no such file in this repository'
    if kind == 'functions':
        rows = sorted((item['line'], item['qual'], item['sig']) for item in graph.functions().values()
                      if item['file'] == argument and '<' not in item['qual'])
        if not rows:
            return '', f'generate functions {argument}: the map reads no functions in {argument}'
        lines = [f'| `{_cell(qual)}` | `{_cell(" ".join(sig.split()))}` |' for _, qual, sig in rows]
        return '\n'.join(['| Function | Signature |', '|---|---|', *lines]), ''
    rows = sorted((row['line'], row['target'], json.dumps(row['value'], ensure_ascii=False)) for row in graph.assignments()
                  if row['file'] == argument and ':' not in row['node'] and not row.get('field') and row.get('literal'))
    if not rows:
        return '', f'generate constants {argument}: no module-level literal constant in {argument}'
    return '\n'.join(['| Constant | Value |', '|---|---|', *(f'| `{_cell(name)}` | `{_cell(value)}` |' for _, name, value in rows)]), ''


def stale(graph, document, text):
    """[(line, kind, argument, problem)] of the regions of one document that differ from what the map gives now
    (problem '') or cannot be generated (an unknown kind or argument, no end marker)."""
    found = []
    for kind, argument, line, _, end, body in regions(text):
        if end is None:
            found.append((line, kind, argument, f'generate {kind} {argument} has no <!-- flowguard: end --> marker'))
            continue
        now, problem = generated(graph, kind, argument)
        if problem or now.strip() != body.strip():
            found.append((line, kind, argument, problem))
    return found


def rewrite(graph):
    """`python -m flowguard docs`: write each generated region of every document from the map. Returns
    [(document, line, kind, argument, problem)] of the regions it rewrote (problem '') or could not write."""
    done = []
    for document in documents(graph.root):
        path = graph.root / document
        raw = path.read_bytes().decode('utf-8-sig')
        newline = '\r\n' if '\r\n' in raw else '\n'
        lines = raw.replace('\r\n', '\n').split('\n')
        changed = False
        for kind, argument, line, start, end, body in reversed(regions(raw.replace('\r\n', '\n'))):
            if end is None:
                done.append((document, line, kind, argument, f'generate {kind} {argument} has no <!-- flowguard: end --> marker'))
                continue
            now, problem = generated(graph, kind, argument)
            if problem:
                done.append((document, line, kind, argument, problem))
            elif now.strip() != body.strip():
                lines[start:end] = now.split('\n')
                changed = True
                done.append((document, line, kind, argument, ''))
        if changed:
            path.write_bytes(newline.join(lines).encode('utf-8'))
    return sorted(done)
