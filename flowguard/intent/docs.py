"""Documents tied to code (design 4.4; R91, R92): a Markdown text that describes code says so with one comment,

    <!-- flowguard: about backend/src/services/allocation.service.ts:allocationService.create -->

and the text from it to the next marker or heading (or, when a heading follows the marker, that heading's section)
describes that site, read as a known.toml site is (`sources.site_resolver`: a function, method, object.method,
constant or Model.field of a file, or a file's path alone). When a change edits the site and not that text, the
block says so with an `impact` line, never a red one: the text may now be out of date, and only a reader can tell.
A marker this change writes with a site that names nothing is red; one that an earlier change left so, or whose site
this change removed, is an `impact` line when this change touches it, and `check --all` lists every one."""
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
    return found
