"""Documents tied to code (design 4.4; R91, R92): a Markdown text that describes code says so with one comment,

    <!-- flowguard: about backend/src/services/allocation.service.ts:allocationService.create -->

and the text from it to the next marker or heading (or, when a heading follows the marker, that heading's section)
describes that site, read as a known.toml site is (`sources.site_resolver`: a function, method, object.method,
constant or Model.field of a file, or a file's path alone). When a change edits the site and not that text, the
block says so with an `impact` line, never a red one: the text may now be out of date, and only a reader can tell.
A marker this change writes with a site that names nothing is red; one that an earlier change left so, or whose site
this change removed, is an `impact` line when this change touches it, and `check --all` lists every one.

A text whose site is a file or a folder (`backend/src/services/`) is that module's contract (R98). A change that edits
a function another module calls, or that calls into another module, names the contracts of those modules too, once
each, when the change leaves their text as it was: the connected module may now work differently. `show PATH` of a
file or folder prints its contracts and the modules it calls and is called by, with theirs (`module_lines`). Both
read the calls the map resolved (`MapHandle.resolved_calls`), never a call matched by a method's name alone.

A list the code already holds is generated instead: the lines between `<!-- flowguard: generate KIND ARG -->` and
`<!-- flowguard: end -->` are written from the map by `python -m flowguard docs` (`rewrite`), and a run whose region
differs from what the map gives now names it with an `impact` line."""
from __future__ import annotations

import os
import re

from flowguard.map.common import git_run, is_test_file, read_source

MARKER = re.compile(r'<!--\s*flowguard:\s*about\s+(\S+?)\s*-->')
HEADING = re.compile(r'(#{1,6})\s')
REVIEW = 'reread that text and correct it if it no longer holds'
FENCE = re.compile(r' {0,3}(`{3,}|~{3,})')
SPAN = re.compile(r'(`+)(?!`).*?(?<!`)\1(?!`)')


def _outside_code(text):
    """The lines of a Markdown text with its code blanked out: the lines of a fenced code block, and each inline code
    span on one line. A marker written as code, as a guide shows the syntax, is text a reader sees, not a comment."""
    lines, fence = [], None
    for line in text.splitlines():
        opening = FENCE.match(line)
        if fence is not None:
            if opening and opening[1][0] == fence[0] and len(opening[1]) >= len(fence) and not line[opening.end():].strip():
                fence = None
            lines.append('')
        elif opening and not (opening[1][0] == '`' and '`' in line[opening.end():]):
            fence = opening[1]
            lines.append('')
        else:
            lines.append(SPAN.sub(lambda match: ' ' * len(match[0]), line))
    return lines


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
    next heading of its level or above. A marker or heading inside code (`_outside_code`) is none."""
    lines, plain = text.splitlines(), _outside_code(text)
    found = []
    for index, line in enumerate(plain):
        match = MARKER.search(line)
        if not match:
            continue
        start = index + 1
        while start < len(lines) and not lines[start].strip():
            start += 1
        heading = HEADING.match(plain[start]) if start < len(lines) else None
        end = start + 1 if heading else start
        while end < len(lines) and not MARKER.search(plain[end]):
            other = HEADING.match(plain[end])
            if other and (not heading or len(other[1]) <= len(heading[1])):
                break
            end += 1
        found.append((match[1], index + 1, '\n'.join(lines[start:end]).strip()))
    return found


def findings(change, touched, *, everything=False):
    """The document findings for `owners.static_findings`: an `impact` line per `about` marker whose site this change
    edits (its node is in `touched`, or `Change.edited` sees a comment inside it) while the text it describes stays as
    it was, and per marker whose site names nothing that this change touches; a red input finding per marker this
    change adds or edits whose site names nothing. A generated region that is out of date, or that cannot be written
    while its marker is older than this change, is an `impact` line when this change edits a file it is generated from
    (`_generated_from`) or the region or its marker itself (`everything`: every one); one this change writes that
    cannot be written is red. Each is counted in `stats['stale_regions']`, those that cannot be written also in
    `stats['unwritable_regions']`, for the session brief (R99). Without a baseline nothing is compared, and no region
    is counted."""
    from .owners import Findings
    from .signals import Line
    from .sources import _input, site_resolver
    found = Findings(stats=dict(stale_regions=0, unwritable_regions=0))
    if not change.baseline:
        return found
    graph, resolve, linked = change.graph, None, None       # both read once, when a marker needs them
    for document in documents(graph.root):
        then = change.old_text(document)
        before = {(site, span) for site, _, span in markers(then)} if then is not None else set()
        sites_then = {site for site, _ in before}
        for site, line, span in markers(read_source(graph.root / document)):
            path = site.rpartition(':')[0] or site
            if ':' not in site:             # a file's or a folder's path alone: the text is that module's contract
                nodes, files = set(), module_files(graph, site)
                problem = '' if files else (f'site {site}: no mapped file in this folder' if site.endswith('/')
                                            else f'site {site}: no such file in this repository')
            else:
                if resolve is None:
                    resolve = site_resolver(graph, change)
                nodes, files, problem = resolve(site)
            place = f'{document}:{line}'
            if problem:
                if site not in sites_then:          # this change wrote the marker
                    found.issues.append(_input(f'docs:{place}', f'about {site}', place, [problem],
                                               f'name one function, constant or Model.field, a file or a folder (path/), in the marker at {place}',
                                               [document]))
                elif everything or path in change.baseline_paths():
                    found.lines.append(Line('impact', f'docs:{place}', '', f'{place} describes {site}, which names nothing now',
                                            'update that text and its marker, or remove them', (place,), (problem,)))
                continue
            edited = bool(nodes & touched) or bool(files & change.files)
            if edited and (site, span) in before:
                found.lines.append(Line('impact', f'docs:{place}', '', f'{place} describes {site}, which this change edits',
                                        REVIEW, (place,), ()))
            elif ':' not in site and (site, span) in before:
                if linked is None:
                    linked = _linked(graph, touched)
                links = [(other, how, node) for other, (how, node, path) in linked.items() if path in files]
                if links:
                    other, how, node = links[0]
                    found.lines.append(Line('impact', f'docs:{place}', '', f'{place} describes {site}, whose '
                                            f'{_site_of(graph, other)} {how} {_site_of(graph, node)}, which this change edits',
                                            REVIEW, (place,), tuple(f'{_site_of(graph, other)} {how} {_site_of(graph, node)}'
                                                                    for other, how, node in links)))
        old_regions = regions(then) if then is not None else []
        regions_then = {(kind, argument) for kind, argument, *_ in old_regions}
        kept = {(kind, argument, body) for kind, argument, _, _, _, body in old_regions}     # as the baseline has them
        for line, kind, argument, body, problem in stale(graph, document, read_source(graph.root / document)):
            place = f'{document}:{line}'
            found.stats['stale_regions'] += 1
            found.stats['unwritable_regions'] += bool(problem)
            if problem and (kind, argument) not in regions_then:      # this change wrote the region
                found.issues.append(_input(f'docs:{place}', f'generate {kind} {argument}', place, [problem],
                                           f'correct the marker at {place}', [document]))
            elif not (everything or (kind, argument, body) not in kept or _generated_from(change, kind, argument)):
                continue            # as an earlier change left it, from sources this change leaves alone (R99)
            elif problem:
                found.lines.append(Line('impact', f'docs:{place}', '', f'{place} generate {kind} {argument} cannot be written',
                                        'correct its marker or remove the region', (place,), (problem,)))
            else:
                found.lines.append(Line('impact', f'docs:{place}', '', f'{place} generate {kind} {argument} is out of date',
                                        'python -m flowguard docs rewrites it', (place,), ()))
    return found


def _generated_from(change, kind, argument):
    """Whether this change edits, adds or removes a file a region of `kind` is generated from (`generated`), as the
    file's map facts read at the baseline and now: for `functions` and `constants` the file the argument names; for
    `fields` a Prisma schema that declares the model; for `values` a file outside tests and archives that declares the
    set (`_declares`: a JS/TS set, a Prisma enum, the Prisma field or a JS/TS member of `Model.field`, a SQL CHECK on
    its column). A file that merely holds the set's or the field's name declares nothing."""
    paths = change.baseline_paths()
    if kind in ('functions', 'constants'):
        return argument in paths
    if kind not in ('fields', 'values'):
        return False
    graph = change.graph
    kinds = ('language', 'schema', 'value_sets', 'typed_fields')
    now = {path: facts for path, _, facts in graph._kinds(*kinds)}
    records = {path: [facts for facts in (change.old_record(path, kinds), now.get(path)) if facts]
               for path in sorted(paths) if change.module(path) is not None}
    if kind == 'fields':
        return any(item['name'] == argument for path, found in records.items() if path.endswith('.prisma')
                   for facts in found for item in (facts.get('schema') or {}).get('models', ()))
    read = [facts for path, found in records.items() if not is_test_file(path) and not graph.archived(path)
            for facts in found]
    names, enums = _set_names(graph, argument, read)
    return any(_declares(graph, facts, argument, names, enums) for facts in read)


def _set_names(graph, argument, extra):
    """(JS/TS set names, Prisma enum names) a `values ARGUMENT` set is read through, now or in the fact records `extra`
    (changed files at the baseline): for `Model.field` the sets its JS/TS members name (`typed_fields`, an alias such
    as `granularity: Granularity`) and the enums its Prisma fields are typed with; for another name that name; then
    the sets each JS/TS alias of one of them names, `(typeof GRANULARITIES)[number]`, as `MapHandle._ts_values`
    follows them."""
    model, dot, field = argument.partition('.')
    names, enums = set(), set()
    if dot and field and '.' not in field:
        records = [facts for _, _, facts in graph._kinds('typed_fields')] + list(extra)
        names = {row['of'] for facts in records for row in facts.get('typed_fields') or ()
                 if row['container'] == model and row['field'] == field and row['kind'] == 'alias'}
        schemas = [schema for schema in graph.schemas() if schema.get('kind') == 'prisma'] + \
            [facts['schema'] for facts in extra if (facts.get('schema') or {}).get('kind') == 'prisma']
        enums = {column['type'] for schema in schemas for item in schema.get('models', ()) if item['name'] == model
                 for column in item.get('fields', ()) if column['name'] == field}
    else:
        names, enums = {argument}, {argument}
    rows = [row for found in graph._ts_sets().values() for row in found] + \
        [row for facts in extra for row in facts.get('value_sets') or ()]
    while True:
        more = {row['of'] for row in rows if row['kind'] == 'alias' and row['name'] in names} - names
        if not more:
            return names, enums
        names |= more


def _declares(graph, facts, argument, names, enums):
    """Whether one file's fact record (now or at the baseline) declares the set a `values ARGUMENT` region is written
    from: a JS/TS set of one of `names` (`_set_names`), a Prisma enum of one of `enums` or, for `Model.field`, a JS/TS
    member of that type and field, the field in a Prisma model (whose type and column a CHECK's set is read through)
    and a SQL CHECK on its column."""
    if any(row['name'] in names for row in facts.get('value_sets') or ()):
        return True
    schema = facts.get('schema') or {}
    if any(enum['name'] in enums for enum in schema.get('enums', ())):
        return True
    model, dot, field = argument.partition('.')
    if not (dot and field and '.' not in field):
        return False
    if any(row['container'] == model and row['field'] == field for row in facts.get('typed_fields') or ()):
        return True
    if schema.get('kind') == 'prisma':
        return any(column['name'] == field for item in schema.get('models', ()) if item['name'] == model
                   for column in item.get('fields', ()))
    models = graph._models()
    for item in [*schema.get('tables', ()), *schema.get('changes', ())]:
        owner = models.table_model(item.get('name') or item['table'])
        for check in item.get('checks', ()):
            column = models.column_field(owner, check['column']) if owner == model else None
            if column is not None and column['name'] == field:
                return True
    return False


# ---- modules: their contracts and connections (R98) ---------------------------------------------------------------

def module_files(graph, site):
    """The files a module site covers: a file's path, that file when it exists (an `about` marker may describe a file
    the map does not read, `docker-compose.yml`); a folder's (`path/`), every mapped file under it. Empty when there
    is none."""
    if site.endswith('/'):
        return {path for (path,) in graph.con.execute('SELECT path FROM file') if path.startswith(site)}
    return {site} if (graph.root / site).is_file() else set()


def _file_of(graph, node):
    row = graph.con.execute('SELECT file FROM node WHERE id = ?', (node,)).fetchone()
    return row[0] if row else ''


def _site_of(graph, node):
    """A function node as `path:qual`, the way a site names it."""
    row = graph.con.execute('SELECT file, qual FROM node WHERE id = ?', (node,)).fetchone()
    return f'{row[0]}:{row[1]}' if row else node


def _linked(graph, touched):
    """{function of another file: (how, edited function, its file)} for the functions this change edits (`touched`): the
    functions of other files that call one ('calls') and those one calls ('is called by'), by the calls the map
    resolved (`MapHandle.resolved_calls`: a call matched by its name alone connects nothing), first edited function
    by id."""
    if not touched:
        return {}
    down, up = graph.resolved_calls()
    linked = {}
    for node in sorted(touched):
        home = _file_of(graph, node)
        for others, how in ((up.get(node, ()), 'calls'), (down.get(node, ()), 'is called by')):
            for other in sorted(others):
                path = _file_of(graph, other)
                if other not in touched and path not in ('', home):
                    linked.setdefault(other, (how, node, path))
    return linked


def module_lines(graph, site):
    """`show PATH` of an existing file or folder (R98): the texts that describe it, then each module (file) it calls
    or is called by, with the number of calls and the texts that describe that module. The calls are those the map
    resolved (`MapHandle.resolved_calls`): a JS/TS member call matched by its name alone (`rows.find`, `days.get`,
    `logger.warn` on an imported object) is not counted. What is no module says so in one line: a Markdown file is a
    document (`document docs/notes/roles.md`), a file the map does not read is no source file (`pyproject.toml`), a
    folder without a file the map reads has none, with the number of Markdown documents under it. The repository's
    root folder `./` holds every mapped file; no about marker names it."""
    if site.endswith('.md'):
        return [f'document {site}']
    if site.endswith('/'):          # the repository's root folder `./` holds every mapped file
        files = module_files(graph, site) if site != './' else {path for (path,) in graph.con.execute('SELECT path FROM file')}
        if not files:
            listed = git_run(graph.root, 'ls-files', '-z', '--cached', '--others', '--exclude-standard', '--',
                             site + '*.md').stdout
            count = len({item for item in listed.split(b'\0') if item})
            return [f'folder {site}: no source file the map reads'
                    + (f'; {count} Markdown document{"s" * (count != 1)}' if count else '')]
    elif not graph.con.execute('SELECT 1 FROM file WHERE path = ?', (site,)).fetchone():
        return [f'{site}: no source file the map reads, and no Markdown document']
    else:
        files = {site}
    contracts = {}          # file -> the places of the markers whose file or folder site covers it
    for document in documents(graph.root):
        for marked, line, _ in markers(read_source(graph.root / document)):
            if ':' not in marked:
                for path in module_files(graph, marked):
                    contracts.setdefault(path, []).append(f'{document}:{line}')
    functions = {node: item for node, item in graph.functions().items() if '<' not in item['qual']}
    mine = [node for node, item in functions.items() if item['file'] in files]
    down, up = graph.resolved_calls()
    outward, inward = {}, {}
    for node in mine:
        for others, into in ((down.get(node, ()), outward), (up.get(node, ()), inward)):
            for other in others:
                path = functions[other]['file'] if other in functions else ''
                if path and path not in files:
                    into[path] = into.get(path, 0) + 1
    def described(path):
        places = contracts.get(path, [])
        return f'; described by {", ".join(dict.fromkeys(places))}' if places else ''
    own = list(dict.fromkeys(place for path in sorted(files) for place in contracts.get(path, [])))
    lines = [f'module {site}: {len(files)} file{"s" * (len(files) != 1)}, {len(mine)} function{"s" * (len(mine) != 1)}']
    lines += [f'described by {place}' for place in own] or ([] if site == './' else [    # no marker names the root
        f'described by no text: put <!-- flowguard: about {site} --> above the Markdown text that is its contract'])
    lines += [f'calls {path} ({count} call{"s" * (count != 1)}{described(path)})' for path, count in sorted(outward.items())]
    lines += [f'called by {path} ({count} call{"s" * (count != 1)}{described(path)})' for path, count in sorted(inward.items())]
    return lines


# ---- generated regions --------------------------------------------------------------------------------------------
# `<!-- flowguard: generate KIND ARG -->` ... `<!-- flowguard: end -->`: the lines between are FlowGuard's, written
# from the map by `python -m flowguard docs`. They carry no line numbers, which an edit above would date.

GENERATE = re.compile(r'<!--\s*flowguard:\s*generate\s+(\S+)\s+(\S+?)\s*-->')
END = re.compile(r'<!--\s*flowguard:\s*end\s*-->')
KINDS = ('fields', 'values', 'functions', 'constants')


def regions(text):
    """[(kind, argument, line, start, end, body)] of a document's generated regions: `line` is the marker's line
    (1-based), the body the lines from `start` to `end` (0-based, `end` the end marker's index, or None when the
    region has no end marker). A marker inside code (`_outside_code`) is none."""
    lines, plain = text.splitlines(), _outside_code(text)
    found = []
    for index, line in enumerate(plain):
        match = GENERATE.search(line)
        if match:
            end = next((other for other in range(index + 1, len(lines)) if END.search(plain[other])
                        or GENERATE.search(plain[other])), None)
            if end is not None and not END.search(plain[end]):
                end = None
            found.append((match[1], match[2], index + 1, index + 1, end,
                          '\n'.join(lines[index + 1:end]).strip('\n') if end is not None else ''))
    return found


def _cell(text):
    return str(text).replace('|', '\\|').replace('\n', ' ').strip()


def generated(graph, kind, argument):
    """(the Markdown of one region, '') or ('', what is wrong): `fields Model` a table of a Prisma model's fields with
    each schema file's type where they differ, `values NAME` the members of the value set declared under that name
    (`owners.value_sets_named`, the sets the values lines of `show NAME` give, but for the enum of a Prisma schema not
    in use: what only test files declare left out; several different sets cannot be written),
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
        from .owners import value_sets_named        # the sets `show NAME` lists as its values lines
        rows = value_sets_named(graph, argument)
        sets = {values for values, _, _, used in rows if used}
        if len(sets) != 1:
            unused = [where for _, where, _, used in rows if not used]
            return '', f'generate values {argument}: ' + (
                f'{len(sets)} different value sets have that name' if sets else
                f'only the enum of a Prisma schema not in use has that name ({"; ".join(unused)})' if unused else
                'no value set of that name')
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
    """[(line, kind, argument, body, problem)] of the regions of one document that differ from what the map gives now
    (problem '') or cannot be generated (an unknown kind or argument, no end marker), with each region's body as
    `regions` reads it."""
    found = []
    for kind, argument, line, _, end, body in regions(text):
        if end is None:
            found.append((line, kind, argument, body, f'generate {kind} {argument} has no <!-- flowguard: end --> marker'))
            continue
        now, problem = generated(graph, kind, argument)
        if problem or now.strip() != body.strip():
            found.append((line, kind, argument, body, problem))
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
