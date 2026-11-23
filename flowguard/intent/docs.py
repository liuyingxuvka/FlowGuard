"""Documents tied to code (design 4.4; R91, R92): a Markdown text that describes code says so with one comment,

    <!-- flowguard: about backend/src/services/allocation.service.ts:allocationService.create -->

and the text from it to the next marker or heading (or, when a heading follows the marker, that heading's section;
markers stacked above one text all describe it) describes that site, read as a known.toml site is
(`sources.site_resolver`: a function, method, object.method, constant or Model.field of a file, or the path alone of
any file, a data file or a generated one too). When a change edits the site and not that text, the
block says so with an `impact` line, never a red one: the text may now be out of date, and only a reader can tell.
A marker this change writes with a site that names nothing is red; one that an earlier change left so, or whose site
this change removed, is an `impact` line when this change touches it, and `check --all` lists every one.

A text whose site is a file or a folder (`backend/src/services/`) is that module's contract (R98). A change that edits
a function another module calls, or that calls into another module, names the contracts of those modules too, once
each, when the change leaves their text as it was: the connected module may now work differently. `show PATH` of a
file or folder prints its contracts and the modules it calls and is called by, with theirs (`module_lines`). Both
read the calls the map resolved (`MapHandle.resolved_calls`: a member call on an imported object whose module defines
that member counts), never a call matched by a method's name alone.

A list the code already holds is generated instead: the lines between `<!-- flowguard: generate KIND ARG -->` and
`<!-- flowguard: end -->` are written from the map by `python -m flowguard docs` (`rewrite`), and a run whose region
differs from what the map gives now names it with an `impact` line."""
from __future__ import annotations

import re

from flowguard.map.common import document_text, git_files, is_test_file

MARKER = re.compile(r'<!--\s*flowguard:\s*about\s+(\S+?)\s*-->')
HEADING = re.compile(r'(#{1,6})\s')
REVIEW = 'reread that text and correct it if it no longer holds'
NO_END = 'no <!-- flowguard: end --> marker ends it'
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


def document(name, data):
    """(text, problem) of a Markdown document's bytes as FlowGuard reads them, through the one reader of project
    documents (`map.common.document_text`: a BOM selects UTF-8 or UTF-16, else UTF-8), with LF newlines; ('', problem)
    when the bytes are no such text, the problem naming the file and the decoder's error."""
    decoded, problem = document_text(name, data)
    return (decoded[0].replace('\r\n', '\n').replace('\r', '\n'), '') if decoded else ('', problem)


def documents(root):
    """The Markdown files of the project (`map.common.git_files`: in Git tracked or not, Git's ignore rules applied;
    outside Git the map's own folder walk) that hold a marker, as `document` reads them; one whose bytes are no UTF-8
    or UTF-16 text is listed when its bytes spell a marker, so that its reader reports why it cannot be read."""
    found = []
    for name in sorted(name for name in git_files(root) if name.endswith('.md')):
        path = root / name
        if path.is_file():
            data = path.read_bytes()
            text, problem = document(name, data)
            if 'flowguard:' in text or problem and b'flowguard:' in data:
                found.append(name)
    return found


def markers(text):
    """[(site, line, span)] of the `about` markers of a document's text: `span` is the text the marker describes, the
    lines after it to the next marker or heading; when a heading follows the marker, that heading's section, to the
    next heading of its level or above. Markers stacked above one text, on lines of their own, all describe that text:
    a checked-in generated file's line marked with its producer and each input file (PEMEL23-11), where 5.0.1 gave
    each marker but the last no text, so that a change to its site named it even when the line was rewritten. A marker
    or heading inside code (`_outside_code`) is none."""
    lines, plain = text.splitlines(), _outside_code(text)
    found = []
    for index, line in enumerate(plain):
        match = MARKER.search(line)
        if not match:
            continue
        start = index + 1
        while start < len(lines) and (not lines[start].strip()
                                      or MARKER.search(plain[start]) and not MARKER.sub('', plain[start]).strip()):
            start += 1          # a blank line, or another marker of a stack above the same text
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
    for name in documents(graph.root):
        old = graph._baseline_bytes(change.baseline, name)
        then = document(name, old)[0] if old is not None else None
        now, unread = document(name, (graph.root / name).read_bytes())
        if unread:
            if everything or name in change.files:
                found.lines.append(Line('impact', f'docs:{name}', '', unread, 'save it as UTF-8 for its markers to be read',
                                        (name,), ()))
            continue
        before = {(site, span) for site, _, span in markers(then)} if then is not None else set()
        sites_then = {site for site, _ in before}
        for site, line, span in markers(now):
            path = site.rpartition(':')[0] or site
            if ':' not in site:             # a file's or a folder's path alone: the text is that module's contract
                nodes, files = set(), module_files(graph, site)
                problem = '' if files else (f'site {site}: no mapped file in this folder' if site.endswith('/')
                                            else f'site {site}: no such file in this repository')
            else:
                if resolve is None:
                    resolve = site_resolver(graph, change)
                nodes, files, problem = resolve(site)
            place = f'{name}:{line}'
            if problem:
                if site not in sites_then:          # this change wrote the marker
                    found.issues.append(_input(f'docs:{place}', f'about {site}', place, [problem],
                                               f'name one function, constant or Model.field, a file or a folder (path/), in the marker at {place}',
                                               [name]))
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
        for line, kind, argument, body, problem in stale(graph, name, now):
            place = f'{name}:{line}'
            found.stats['stale_regions'] += 1
            found.stats['unwritable_regions'] += bool(problem)
            if problem and (kind, argument) not in regions_then:      # this change wrote the region
                found.issues.append(_input(f'docs:{place}', f'generate {kind} {argument}', place, [problem],
                                           f'correct the marker at {place}', [name]))
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
    """Whether this change edits, adds or removes what a region of `kind` is generated from (`generated`): for
    `functions` and `constants` the file the argument names; for `fields` and `values` the declaration facts of the
    model or the set, read per file from the map at the baseline and now, which must differ: for `fields` the model's
    fields with their types and columns in a Prisma schema, for `values` what a file outside tests and archives
    declares of the set (`_declaration`: a JS/TS set's members, a Prisma enum's, the Prisma field's type and column
    or a JS/TS member's type of `Model.field`, a SQL CHECK's set on its column). A comment or any other edit of a file
    that declares the set changes nothing of it, and a file that merely holds the set's or the field's name declares
    nothing."""
    paths = change.baseline_paths()
    if kind in ('functions', 'constants'):
        return argument in paths
    if kind not in ('fields', 'values'):
        return False
    graph = change.graph
    kinds = ('language', 'schema', 'value_sets', 'typed_fields')
    now = {path: facts for path, _, facts in graph._kinds(*kinds)}
    records = {path: (change.old_record(path, kinds), now.get(path)) for path in sorted(paths)
               if change.module(path) is not None}
    if kind == 'fields':
        def fields(facts):
            return [[(column['name'], column['type'], column['list'], column['optional'], column['column'])
                     for column in item['fields']] for item in ((facts or {}).get('schema') or {}).get('models', ())
                    if item['name'] == argument]
        return any(fields(then) != fields(current) for path, (then, current) in records.items() if path.endswith('.prisma'))
    read = [pair for path, pair in records.items() if not is_test_file(path) and not graph.archived(path)]
    names, enums = _set_names(graph, argument, [facts for pair in read for facts in pair if facts])
    return any(_declaration(graph, then, argument, names, enums) != _declaration(graph, current, argument, names, enums)
               for then, current in read)


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


def _declaration(graph, facts, argument, names, enums):
    """What one file's fact record (now or at the baseline; None when the file does not exist then) declares of the
    set a `values ARGUMENT` region is written from, without positions: the JS/TS sets of one of `names` (`_set_names`)
    with their kind, members and the set an alias names, the Prisma enums of one of `enums` with their members and,
    for `Model.field`, the JS/TS members of that type and field with their types, the field in a Prisma model with
    its type and column (through which a CHECK's set is read) and the set of each SQL CHECK on its column. Empty when
    the file declares nothing of it."""
    if not facts:
        return []
    found = [('set', row['name'], row['kind'], row.get('values'), row.get('members'), row.get('of'))
             for row in facts.get('value_sets') or () if row['name'] in names]
    schema = facts.get('schema') or {}
    found += [('enum', enum['name'], [member['name'] for member in enum['fields']])
              for enum in schema.get('enums', ()) if enum['name'] in enums]
    model, dot, field = argument.partition('.')
    if not (dot and field and '.' not in field):
        return found
    found += [('member', row['container'], row['field'], row['kind'], row.get('values'), row.get('of'))
              for row in facts.get('typed_fields') or () if row['container'] == model and row['field'] == field]
    if schema.get('kind') == 'prisma':
        return found + [('field', item['name'], column['name'], column['type'], column['column'])
                        for item in schema.get('models', ()) if item['name'] == model
                        for column in item.get('fields', ()) if column['name'] == field]
    models = graph._models()
    for item in [*schema.get('tables', ()), *schema.get('changes', ())]:
        table = item.get('name') or item['table']
        owner = models.table_model(table)
        for check in item.get('checks', ()):
            column = models.column_field(owner, check['column']) if owner == model else None
            if column is not None and column['name'] == field:
                found.append(('check', table, check['column'], check['values']))
    return found


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


def _marks(graph):
    """([(document, line, site)] of the about markers of every document the repository holds, [(document, line, kind,
    argument)] of its generated regions, [what is wrong with each document whose bytes are no UTF-8 or UTF-16 text:
    its markers are not read])."""
    found, generating, unread = [], [], []
    for name in documents(graph.root):
        text, problem = document(name, (graph.root / name).read_bytes())
        if problem:
            unread.append(f'{problem}; its about markers are not read')
        found.extend((name, line, site) for site, line, _ in markers(text))
        generating.extend((name, line, kind, argument) for kind, argument, line, *_ in regions(text))
    return found, generating, unread


def described_by(graph, places, models=()):
    """`show NAME` of a function, method, constant or Model.field (5.0 gate: Planning Tool's `show
    resolveFullPspNumber` did not say that a text describes it): `described by DOC:LINE (about SITE)` for each about
    marker whose site names one of `places`, [(file, names, node)]: that file, a folder holding it, or `file:name` for
    one of its names that the one reading of a site (`sources.site_resolver`, as `check --static` reads the marker)
    resolves without a problem, to that node when the place has one (GA-0: a marker `capacity.service.ts:getUtilization`,
    which names nothing because the method is `capacityService.getUtilization`, describes nothing); and `described by
    DOC:LINE (generate KIND ARG)` for each generated region that lists one (gate-5): a `functions` or `constants` region
    of that file that writes a row of one of its names (`listed`), a `fields` region of one of `models`. In document and
    line order, then a line for each document whose markers cannot be read. Nothing is read when there is no place and
    no model."""
    if not places and not models:
        return []
    from .sources import site_resolver
    found, generating, unread = _marks(graph)
    resolve, rows, lines = None, {}, []
    for name, line, site in found:
        path, colon, symbol = site.rpartition(':')
        if colon:
            hits = [node for file, names, node in places if path == file and symbol in names]
            if not hits:
                continue
            resolve = resolve or site_resolver(graph)
            nodes, _, problem = resolve(site)
            if problem or not any(node is None or node in nodes for node in hits):
                continue
        elif not any(site == file or site.endswith('/') and file.startswith(site) for file, _, _ in places):
            continue
        lines.append((name, line, f'about {site}'))
    for name, line, kind, argument in generating:
        if kind == 'fields' and argument in models or kind in ('functions', 'constants') and any(
                file == argument and names & rows.setdefault((kind, file), listed(graph, kind, file))
                for file, names, _ in places):
            lines.append((name, line, f'generate {kind} {argument}'))
    order = {name: index for index, name in enumerate(dict.fromkeys(item[0] for item in [*found, *generating]))}
    lines.sort(key=lambda item: (order[item[0]], item[1]))
    return list(dict.fromkeys(f'described by {name}:{line} ({what})' for name, line, what in lines)) + unread


def module_lines(graph, site):
    """`show PATH` of an existing file or folder (R98), as (its first line, the texts that describe it, the rest):
    `described by DOC:LINE (about SITE)` for each marker whose file or folder site covers a file of it, with the site it
    names, and `described by DOC:LINE (generate KIND path)` for each generated region that lists the functions or
    constants of one of its files (gate-5: such a file gets no `described by no text` advice); then each module (file)
    it calls or is called by, with the number of calls and the texts that describe that module (a folder's site named, a
    region's kind: `described by DOC:LINE generate functions`). The calls are those the map resolved
    (`MapHandle.resolved_calls`), from any function of those files, a callback too: `logger.warn(...)` on a `logger`
    imported from the module that defines it counts, a JS/TS member call matched by its name alone (`rows.find`,
    `days.get`) does not. What is no module says so in its first line: a Markdown file is a document (`document
    docs/notes/roles.md`), whose about markers (`DOC:LINE describes SITE`, and whether the site names nothing) and
    generated regions (`DOC:LINE generate KIND ARG` and whether it is up to date) follow; a file the map does not read
    is no source file (`pyproject.toml`); a folder without a file the map reads has none, with the number of Markdown
    documents under it. The repository's root folder `./` holds every mapped file; no about marker names it."""
    if site.endswith('.md'):
        return [f'document {site}'], [], document_lines(graph, site)
    if site.endswith('/'):          # the repository's root folder `./` holds every mapped file
        files = module_files(graph, site) if site != './' else {path for (path,) in graph.con.execute('SELECT path FROM file')}
        if not files:
            count = sum(name.startswith(site) and name.endswith('.md') for name in git_files(graph.root))
            return [f'folder {site}: no source file the map reads'
                    + (f'; {count} Markdown document{"s" * (count != 1)}' if count else '')], [], []
    elif not graph.con.execute('SELECT 1 FROM file WHERE path = ?', (site,)).fetchone():
        return [f'{site}: no source file the map reads, and no Markdown document'], [], []
    else:
        files = {site}
    contracts = {}          # file -> (place, site) of the markers whose file or folder site covers it
    found, generating, unread = _marks(graph)
    for name, line, marked in found:
        if ':' not in marked:
            for path in module_files(graph, marked):
                contracts.setdefault(path, []).append((f'{name}:{line}', marked))
    for name, line, kind, argument in generating:      # gate-5: a region that lists a file's functions or constants
        if kind in ('functions', 'constants'):
            contracts.setdefault(argument, []).append((f'{name}:{line}', f'generate {kind} {argument}'))
    functions = graph.functions()
    mine = [node for node, item in functions.items() if item['file'] in files]       # a callback's calls count too
    named = sum('<' not in functions[node]['qual'] for node in mine)
    down, up = graph.resolved_calls()
    outward, inward = {}, {}
    for node in mine:
        for others, into in ((down.get(node, ()), outward), (up.get(node, ()), inward)):
            for other in others:
                path = functions[other]['file'] if other in functions else ''
                if path and path not in files:
                    into[path] = into.get(path, 0) + 1
    def described(path):            # a folder's text says which folder it describes, a region its kind
        places = [place + (f' {marked.rpartition(" ")[0]}' if marked.startswith('generate ') else
                           f' about {marked}' if marked != path else '') for place, marked in contracts.get(path, [])]
        return f'; described by {", ".join(dict.fromkeys(places))}' if places else ''
    own = list(dict.fromkeys(f'described by {place} ({marked if marked.startswith("generate ") else "about " + marked})'
                             for path in sorted(files) for place, marked in contracts.get(path, [])))
    head = [f'module {site}: {len(files)} file{"s" * (len(files) != 1)}, {named} function{"s" * (named != 1)}']
    rest = [] if own or site == './' else [       # no marker names the root
        f'described by no text: put <!-- flowguard: about {site} --> above the Markdown text that is its contract']
    rest += [f'calls {path} ({count} call{"s" * (count != 1)}{described(path)})' for path, count in sorted(outward.items())]
    rest += [f'called by {path} ({count} call{"s" * (count != 1)}{described(path)})' for path, count in sorted(inward.items())]
    return head, own, rest + unread


def document_lines(graph, name):
    """`show DOC` of a Markdown document (5.0 gate: Planning Tool's `show docs/FUNCTION_INVENTORY.md` printed only its
    first line): each about marker, `DOC:LINE describes SITE` (`, which names nothing: ...` when its site names nothing,
    read as `findings` reads it), then each generated region, `DOC:LINE generate KIND ARG` with whether it is up to date
    (`stale`): `is up to date`, `is out of date -> python -m flowguard docs rewrites it`, or `cannot be written: ...`.
    A document whose bytes are no UTF-8 or UTF-16 text says so instead."""
    from .sources import site_resolver
    text, problem = document(name, (graph.root / name).read_bytes())
    if problem:
        return [f'{problem}; its about markers are not read']
    lines, resolve = [], None
    for site, line, _ in markers(text):
        if ':' not in site:
            files = module_files(graph, site)
            absent = '' if files else (f'site {site}: no mapped file in this folder' if site.endswith('/')
                                       else f'site {site}: no such file in this repository')
        else:
            resolve = resolve or site_resolver(graph)
            absent = resolve(site)[2]
        lines.append(f'{name}:{line} describes {site}' + (f', which names nothing: {absent}' if absent else ''))
    out_of_date = {line: problem for line, _, _, _, problem in stale(graph, name, text)}
    for kind, argument, line, *_ in regions(text):
        state = ('is up to date' if line not in out_of_date else
                 f'cannot be written: {out_of_date[line]}' if out_of_date[line] else
                 'is out of date -> python -m flowguard docs rewrites it')
        lines.append(f'{name}:{line} generate {kind} {argument} {state}')
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
    """(the Markdown of one region, '') or ('', what is wrong, without the region's `generate KIND ARG`, which each
    caller prints before it): `fields Model` a table of a Prisma model's fields with
    each schema file's type where they differ and each scalar field's column (a relation field has none: its cell is
    `relation Model`), `values NAME` the members of the value set declared under that name
    (`owners.value_sets_named`, the sets the values lines of `show NAME` give, but for the enum of a Prisma schema not
    in use: what only test files declare left out; the Prisma enum of a schema in use when there is one, else the JS/TS
    sets; sets with the same members in another order are one set; several different sets cannot be written),
    `functions path` the functions and methods of one file that no other function holds (a closure or a callback is
    left out), each by the name a flowguard comment or `show` resolves (`anchors._declared_name`: `service.save` for
    a member of an object, never a line number) with its whole signature as declared, and `constants path` the
    module-level literal constants with their values of one file."""
    if kind not in KINDS:
        return '', f'the kinds are {", ".join(KINDS)}'
    if kind == 'fields':
        found = [(schema['file'], item) for schema in graph.schemas() if schema['kind'] == 'prisma'
                 for item in schema.get('models', ()) if item['name'] == argument]
        if not found:
            return '', f'no Prisma model {argument}'
        from ..structure.readers.prisma import is_column
        models = graph._models().by_name
        order, types, columns = [], {}, {}
        for file, item in sorted(found, key=lambda pair: pair[0]):
            for column in item.get('fields', ()):
                name = column['name']
                if name not in types:
                    order.append(name)
                text = column['type'] + ('[]' if column.get('list') else '') + ('?' if column.get('optional') else '')
                types.setdefault(name, {}).setdefault(text, []).append(file)
                # A relation field has no column of its own: its cell names the model it relates to.
                columns.setdefault(name, (column.get('column') or name) if is_column(column, models)
                                   else f'relation {column["type"]}')
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
        # The Prisma enum of a schema in use is the set the database holds: a JS/TS mirror of it is not another set.
        # Sets with the same members in another order are one set, written in the order of the first.
        used = [values for values, _, _, used, _ in rows if used]
        chosen = [values for values, _, _, used, enum in rows if used and enum] or used
        sets = list(dict.fromkeys(frozenset(values) for values in chosen))
        if len(sets) != 1:
            unused = [where for _, where, _, used, _ in rows if not used]
            return '', (
                f'{len(sets)} different value sets have that name' if sets else
                f'only the enum of a Prisma schema not in use has that name ({"; ".join(unused)})' if unused else
                'no value set of that name')
        return '\n'.join(f'- `{value}`' for value in chosen[0]), ''
    if not (graph.root / argument).is_file():
        return '', 'no such file in this repository'
    if kind == 'functions':
        rows = _function_rows(graph, argument)
        if not rows:
            return '', f'the map reads no functions in {argument}'
        lines = [f'| `{_cell(qual)}` | `{_cell(" ".join(sig.split()))}` |' for _, qual, sig in rows]
        return '\n'.join(['| Function | Signature |', '|---|---|', *lines]), ''
    rows = _constant_rows(graph, argument)
    if not rows:
        return '', f'no module-level literal constant in {argument}'
    return '\n'.join(['| Constant | Value |', '|---|---|', *(f'| `{_cell(name)}` | `{_cell(value)}` |' for _, name, value in rows)]), ''


def _function_rows(graph, path):
    """[(line, name, signature)] of a `functions path` region: the functions and methods of the file that no other
    function holds, each by the name a flowguard comment or `show` resolves (`anchors._declared_name`)."""
    from ..structure import store
    from .anchors import _declared_name
    own = [item for item in graph.functions().values() if item['file'] == path]

    def start(item):
        return item['line'], item.get('column') or 0

    def end(item):
        return item['end_line'] or item['line'], item.get('end_column') or 0

    def nested(item):          # inside another function or method of the file: a closure, a callback
        return any(other is not item and start(other) <= start(item) and end(item) <= end(other)
                   and (start(other), end(other)) != (start(item), end(item)) for other in own)
    raw = {node: store.unpack(data) if data else {} for node, data in graph.con.execute(
        'SELECT id, raw FROM node WHERE file = ?', (path,))}
    rows = sorted((item['line'], _declared_name(path, item['qual'], raw.get(item['id'], {})), item['sig'])
                  for item in own if not nested(item))
    return [row for row in rows if '<' not in row[1]]


def _constant_rows(graph, path):
    """[(line, name, value as JSON)] of a `constants path` region: the module-level literal constants of the file."""
    import json
    return sorted((row['line'], row['target'], json.dumps(row['value'], ensure_ascii=False)) for row in graph.assignments()
                  if row['file'] == path and ':' not in row['node'] and not row.get('field') and row.get('literal'))


def listed(graph, kind, path):
    """The names a `functions path` or `constants path` region writes a row for, as `generated` writes them."""
    return {name for _, name, _ in (_function_rows if kind == 'functions' else _constant_rows)(graph, path)}


def stale(graph, document, text):
    """[(line, kind, argument, body, problem)] of the regions of one document that differ from what the map gives now
    (problem '') or cannot be generated (an unknown kind or argument, no end marker), with each region's body as
    `regions` reads it."""
    found = []
    for kind, argument, line, _, end, body in regions(text):
        if end is None:
            found.append((line, kind, argument, body, NO_END))
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
        decoded, problem = document_text(document, path.read_bytes())
        if decoded is None:
            done.append((document, 0, '', '', problem))
            continue
        raw, bom, encoding = decoded
        newline = '\r\n' if '\r\n' in raw else '\n'
        lines = raw.replace('\r\n', '\n').split('\n')
        changed = False
        for kind, argument, line, start, end, body in reversed(regions(raw.replace('\r\n', '\n'))):
            if end is None:
                done.append((document, line, kind, argument, NO_END))
                continue
            now, problem = generated(graph, kind, argument)
            if problem:
                done.append((document, line, kind, argument, problem))
            elif now.strip() != body.strip():
                lines[start:end] = now.split('\n')
                changed = True
                done.append((document, line, kind, argument, ''))
        if changed:
            path.write_bytes(bom + newline.join(lines).encode(encoding))
    return sorted(done)
