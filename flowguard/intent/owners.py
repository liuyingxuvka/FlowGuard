"""Owners and copies: one owner per judgment or field, and what this change does to the rest.

A reference (`# flowguard: same NAME ref`) is the function its same-name copies (`same NAME`) follow; the
existing same-name comparison checks those. Copy discovery runs unregistered look-alikes on the
reference's case classes, through the runtime's source-only sealed executor, only in
`check`. A writers agreement (`writers Table.column f,g`) makes a write outside its writers a finding.
Every finding names its members, those this change added fresh (`signals.deliver` gives each its line).
Grouping is a finite sample of representative values, never a proof of equal behavior.
"""
from __future__ import annotations

import ast
from collections import Counter
from contextlib import contextmanager
import ctypes
from dataclasses import dataclass, field
import os
import re
import threading
import time

from flowguard.map.common import git_blob, git_renames, git_run, is_test_file, read_source

SIMILAR_SHAPE = 0.5          # 3-gram Jaccard of two function bodies that counts as a similar structure
TRIVIAL = {0, 1, -1, 2}      # numbers too common to tie two functions together
TIMEOUT = 2.0                # seconds for one function's replay before it is listed as unclear
PEERS = 40                   # look-alikes of one changed function replayed at most, the most similar first


@dataclass
class Findings:
    """What the map checks found, for the 4.3 lines (`signals.deliver`): the findings with their members, the lines
    already of their kind, what this change touches and which families ran; and the session brief's count of open
    structure problems."""
    stats: dict = field(default_factory=dict)
    issues: list = field(default_factory=list)      # health.Issue: open structure problems, old ones too
    summary: dict | None = None                     # count and heaviest names for the session brief
    known: list = field(default_factory=list)       # sources.Known: the entries of known.toml, sites resolved
    lines: list = field(default_factory=list)       # signals.Line of their final kind (impact, loosened, not compared)
    ran: set = field(default_factory=set)           # the families whose checks judged the whole project in this run
                                                    # (a known entry's `known fixed?`; `families_ran`)
    touched_functions: frozenset = frozenset()      # what this change edits or adds: a finding's member there is
    touched_files: frozenset = frozenset()          # touched (`deliver`); files for a file-level member

    def extend(self, other):
        self.issues.extend(other.issues)
        self.known.extend(other.known)
        self.lines.extend(other.lines)
        self.ran |= other.ran
        self.touched_functions |= other.touched_functions
        self.touched_files |= other.touched_files
        for key, value in other.stats.items():
            self.stats[key] = self.stats.get(key, 0) + value
        return self


def _ascii(text):
    """A legacy FlowGuard text with its full-width punctuation written in ASCII (project names stay as they are)."""
    for wide, plain in (('\u3001', ', '), ('\uff1b', '; '), ('\uff1a', ': '), ('\uff08', ' ('), ('\uff09', ')'), ('\uff0c', ', '),
                        ('\u2192', '->')):
        text = text.replace(wide, plain)
    return text


def place(row):
    """A write or query row's place, as known.toml and the 4.3 lines spell one: `path:function`, or `path:line` for a
    module's own code."""
    symbol = row_function(row).partition(':')[2]
    return f'{row["file"]}:{symbol}' if symbol else f'{row["file"]}:{row["line"]}'


SEEDING = re.compile(r'(?i:seed|backfill|migration)s?(?![a-z])')


def seeding(path):
    """Is this a seed, backfill or migration script (a folder or the file's stem `seed`, `seeds`, `backfill...`,
    `migrations`, `seedUsers`, `seed-demo`)? Their writes fill or reshape data once; impact counts leave them out."""
    parts = path.split('/')
    return any(SEEDING.match(part) for part in [*parts[:-1], parts[-1].partition('.')[0]])


# ---- the change: baseline commit, changed files and their facts at the baseline ---------------------

class Change:
    """The working tree against one baseline commit, read once; no baseline means nothing is new."""

    def __init__(self, cfg, graph, baseline):
        self.cfg, self.graph = cfg, graph
        self.baseline = graph._baseline_revision(baseline) if baseline else None
        self.files = set(graph._git_changed(self.baseline)) if self.baseline else set()
        self._modules = {path: module for path, module in graph.con.execute('SELECT path, module FROM file')}
        self._texts, self._facts, self._delta, self._impact = {}, {}, {}, None
        self._baseline_writes, self._current, self._definitions = {}, {}, None
        self._held = {}

    def held(self, key, compute):
        """One result of this check, computed once (`compute()`) and kept with the change, for the checks that each
        need it (the copies at the baseline)."""
        if key not in self._held:
            self._held[key] = compute()
        return self._held[key]

    def impact(self):
        """The map's changed, added and removed ids against the baseline (read once)."""
        if self._impact is None:
            self._impact = self.graph.impact(since=self.baseline) if self.baseline else dict(changed=[], added=[], removed=[])
        return self._impact

    def touched(self):
        """Functions (named, nested callbacks folded into them) this change edits or adds, and each JS/TS module-level
        callback it edits or adds by the id a pair member names it by (`_member`: a route handler is a member of its
        own)."""
        if not hasattr(self, '_touched'):
            from flowguard.structure.api import _without_moves
            delta = self.delta(sorted(self.files)) if self.baseline else []
            edited = [ident for ident, change, *_ in _without_moves(delta) if change in ('changed', 'added')]
            self._touched = {named(ident) for ident in edited} | {_member(ident) for ident in edited
                                                                  if _member(ident) != named(ident)}
        return self._touched

    def edited(self, ident):
        """Whether this change edits the text of the function or method `ident` (map id) of a file it changes: a line
        from its first to its last differs from the baseline's, a comment or blank line inside it too, or the baseline
        lacks it. Its code alone is `touched`; a known entry's site is touched by either (D31)."""
        node = self.graph.node(ident)
        if node is None or node['file'] not in self.files:
            return False
        file = node['file']
        old = next((item for item in self.old_facts(file).get('nodes', ()) if item['qual'] == node['qual']), None)
        then = self.old_text(file)
        if old is None or then is None:
            return True
        now = read_source(self.graph.root / file).splitlines()
        return now[node['line'] - 1:node['end_line']] != then.splitlines()[old['line'] - 1:old['end']]

    def delta(self, files):
        """The map's delta rows of these files against the baseline, in their order; each file's rows are read
        once per check."""
        missing = [file for file in dict.fromkeys(files) if file not in self._delta]
        if missing:
            found = dict(self.graph._file_deltas(self.baseline, missing))
            self._delta.update({file: found.get(file, []) for file in missing})     # no reader: no rows
        return [row for file in files for row in self._delta[file]]

    def writes(self):
        """Every write row of the map, read once per check; Python right sides are not folded (the structure
        checks ask who writes; a JS/TS or SQL row keeps the literal values its source spells)."""
        if not hasattr(self, '_writes'):
            self._writes = self.graph.writes(by_name=True, fold=False)
        return self._writes

    def old_text(self, file):
        if file not in self._texts:
            raw = self.graph._baseline_bytes(self.baseline, file) if self.baseline else None
            self._texts[file] = raw.decode('utf-8-sig', errors='replace') if raw is not None else None
        return self._texts[file]

    def renamed(self):
        """{old path: new path} of the renames Git reports between the baseline and the working tree (a rename
        staged with `git mv`; an untracked file is no rename to Git), as `git_renames` reads them. Read once."""
        if not hasattr(self, '_renamed'):
            found = git_renames(self.graph.root, self.baseline) if self.baseline else {}
            self._renamed = {old: new for new, old in found.items()}
        return self._renamed

    def baseline_paths(self):
        """The paths whose baseline side this change alters: `files`, and the old path of a staged rename, which
        `files` (Git's rename detection) names by its new path only. Read once."""
        if not hasattr(self, '_baseline_paths'):
            listed = git_run(self.graph.root, 'diff', '--name-only', '-z', '--relative', '--no-renames', self.baseline,
                             '--').stdout if self.baseline else b''
            self._baseline_paths = frozenset(self.files | {os.fsdecode(name) for name in listed.split(b'\0') if name})
        return self._baseline_paths

    def module(self, file):
        """The module the map names `file` by; for a file the working tree no longer holds (this change deletes it or
        renames it away) the name `graph.impact` gives it (`_file_deltas`). None for a file the map does not read,
        such as one its ignore patterns leave out (`store.ignored`), which it did not read at the baseline either."""
        from flowguard.map.common import matches_any
        from flowguard.structure.readers.registry import language_for, module_name
        from flowguard.structure.store import ignored
        if file in self._modules:
            return self._modules[file]
        language = language_for(file)
        if not language or (self.graph.root / file).exists():
            return None
        if not hasattr(self, '_ignored'):
            self._ignored = ignored(self.graph.root)
        if matches_any(file, self._ignored):
            return None
        return file[:-3].replace('/', '.') if language == 'python' else module_name(file)

    def old_facts(self, file):
        """The map facts the same extractor reads from the file's baseline bytes ({} when it was absent, or when
        the map does not read the file)."""
        if file not in self._facts:
            module = self.module(file)
            self._facts[file] = self.graph._baseline_facts(self.baseline, file, module, is_test_file(file)) \
                if self.baseline and module else {}
        return self._facts[file]

    def old_part(self, file, kind):
        """One kind of `old_facts(file)` (None when absent), read without decoding the file's whole record."""
        module = self.module(file)
        return self.graph._baseline_part(self.baseline, file, module, kind, is_test_file(file)) \
            if self.baseline and module else None

    def old_record(self, file, kinds):
        """The `kinds` of `old_facts(file)` that it holds ({} as it), without decoding the file's whole record unless
        it is decoded already."""
        if file in self._facts:
            return {kind: self._facts[file][kind] for kind in kinds if kind in self._facts[file]}
        module = self.module(file)
        return self.graph._baseline_record(self.baseline, file, module, kinds, is_test_file(file)) \
            if self.baseline and module else {}

    def baseline_definitions(self):
        """The value sets, constants and schema models of the baseline (`graph.definitions`): those of each path of
        `baseline_paths` read from its baseline facts, the map's for every other file. Built once."""
        if self._definitions is None:
            # the kinds `Definitions` reads
            self._definitions = self.graph.definitions(
                [(path, self.module(path), self.old_record(path, ('value_sets', 'schema', 'language', 'nodes', 'facts')))
                 for path in sorted(self.baseline_paths())])
        return self._definitions

    def baseline_writes(self, target=None, *, by_name=False):
        """`graph.writes(target, by_name=)` as the baseline had them: the facts of every file this change leaves
        alone, and those the same reader finds in the baseline bytes of each path of `baseline_paths` (a file this
        change adds has none; one it deletes or renames away has its old ones), with the values and models resolved
        by the baseline's own definitions (`baseline_definitions`: a set, a constant or a schema this change alters
        gives its old value or binding). Read once per target and spelling."""
        key = (target, by_name)
        if key not in self._baseline_writes:
            paths = self.baseline_paths()
            if paths:
                facts = [data for path, _, data in self.graph.write_records() if path not in paths]
                facts += [record for path in sorted(paths)       # the kinds `writes(facts=)` reads
                          if (record := self.old_record(path, ('language', 'writes', 'assignments')))]
                self._baseline_writes[key] = self.graph.writes(target, by_name=by_name, facts=facts,
                                                               definitions=self.baseline_definitions())
            else:
                self._baseline_writes[key] = self.graph.writes(target, by_name=by_name)
        return self._baseline_writes[key]

    def facts(self, file, *, old=False):
        """The whole fact record of `file` now (the map's; None when the map does not read it) or (`old`) at the
        baseline: `old_facts` for a path of `baseline_paths`, the map's for any other file, which this change leaves
        alone. Read once."""
        if old and file in self.baseline_paths():
            return self.old_facts(file)
        if file not in self._current:
            self._current[file] = self.graph.file_facts(file)
        return self._current[file]

    def path_of(self, module, *, old=False):
        """The path of a module on the map, or (`old`) also of one this change deletes or renames away (`module`);
        None for any other."""
        if not hasattr(self, '_paths'):
            self._paths = {name: path for path, name in self._modules.items()}
            self._gone_paths = {}
            for path in sorted(self.baseline_paths() - set(self._modules)):
                self._gone_paths.setdefault(self.module(path), path)
        return self._paths.get(module) or (self._gone_paths.get(module) if old else None)

    def calls(self, file, *, old=False):
        """{node: frozenset of names}: what each node of `file` calls as its source spells it, now or (`old`) at the
        baseline (`facts`): its syntax calls by the node that makes them, in any language, and for a Python function
        also the callables it passes on (`run(save)`, `facts.functions[qual].calls`, as the call index reads them;
        a module's own code and a test file have syntax calls alone). {} for a file the map does not read or that
        does not parse. Read once per file and side."""
        key = (file, old)
        if not hasattr(self, '_calls'):
            self._calls = {}
        if key not in self._calls:
            facts = self.facts(file, old=old)
            found = {}
            for call in (facts or {}).get('syntax_calls', ()):
                found.setdefault(call['node'], set()).add(call['text'])
            if facts and facts['language'] == 'python' and facts['facts']:
                module = self.module(file) if old else self._modules.get(file)
                for function, data in facts['facts']['functions'].items():
                    found.setdefault(f'{module}:{function}', set()).update(data['calls'])
            self._calls[key] = {node: frozenset(names) for node, names in found.items()}
        return self._calls[key]

    def callees(self, ident, *, old=False):
        """The names the function `ident` (`module:qual`; a module's own code for `module`) calls as its source
        spells them, the functions nested in it included, now or (`old`) at the baseline (`calls`). A function of no
        mapped file (at the baseline: of no file this change deletes or renames away either), absent from its file or
        in a file that does not parse calls nothing."""
        module, _, qual = ident.partition(':')
        file = self.path_of(module, old=old)
        if file is None:
            return frozenset()
        return frozenset(name for node, names in self.calls(file, old=old).items()
                         if node == ident or qual and node.startswith(ident + '.') for name in names)


def named(ident):
    """A function id without its anonymous callback parts: a callback's writes and calls are its function's."""
    module, _, qual = ident.partition(':')
    return module + (':' + '.'.join(part for part in qual.split('.') if not part.startswith('<anonymous')) if qual else '')


def row_function(row):
    """The named function id of a write or query row (`module:function`)."""
    module = row['node'].partition(':')[0]
    return named(row['node']) if row.get('language', 'python') == 'python' else \
        module + (':' + row['function'] if row.get('function') and row['function'] != '<module>' else '')


def baseline(cfg, base=None):
    """The comparison commit: an explicit --base, else the task baseline (cache.session_baseline)."""
    from . import cache
    return base or cache.session_baseline(cfg)


# ---- data owners --------------------------------------------------------------------------------------

def _allowed(row, writers):
    """Whether one of `writers` (positions `module:function`) wrote `row`: its own code or a callback inside it (a
    transaction's arrow function writes for the method that passes it)."""
    return named(row['node']) in writers


def _write_key(row):
    return row['file'], row['function'], row['kind'], str(row.get('model') or row.get('table')), str(row.get('field') or row.get('db_column'))


def _agreement_place(graph, owner, role):
    """A role's original declaration, before complementary data agreements were combined."""
    facts = graph.file_facts(owner.file)
    rows = [row for row in facts.get('anchors', ()) if row['kind'] == 'owner' and row['name'] == owner.name
            and not row['qual'] and row.get(role)] if facts is not None else []
    if len(rows) == 1:
        return f'{owner.file}:{rows[0]["line"]}'
    return f'canonical registration {owner.file}:{owner.line}'


def _test_write(graph, row, tests=None):
    """Whether a write row is a test's own (a fixture): not held to a writers agreement, as not to a pair."""
    if tests is None:
        tests = {path for (path,) in graph.con.execute('SELECT path FROM file WHERE is_test = 1')}
    return row['file'] in tests or is_test_file(row['file'])


def owner_writes(change, index):
    """The `writer:` finding of each data owner's writers agreement that production code writes outside
    (`_writer_issue`); a test's own write is a fixture, not held to it (`_test_write`)."""
    found, written = Findings(ran={'writer'}), None
    tests = {path for (path,) in change.graph.con.execute('SELECT path FROM file WHERE is_test = 1')}
    for owner in (a for a in index.entries if a.kind == 'owner' and a.writers):
        if written is None:
            written = change.graph.writes(by_name=True)        # read once for every owner
        rows = [row for row in change.graph.writes_to(written, owner.name)
                if not row.get('unclear') and not _test_write(change.graph, row, tests)]
        outside = [row for row in rows if not _allowed(row, owner.writers)]
        if outside:
            found.issues.append(_writer_issue(change, owner, outside, _agreement_place(change.graph, owner, 'writers')))
    return found


def _member(ident):
    """The name the pair operation gives a function id: `named(ident)`, except that a JS/TS module-level callback
    (`module:<anonymous@L,C>...`, such as a route handler) keeps its outermost part: each handler is its own
    operation, not one `<module>` with every other handler of its file."""
    module, _, qual = ident.partition(':')
    head = qual.split('.')[0]
    return f'{module}:{head}' if head.startswith('<anonymous') else named(ident)


def _writer_name(writer):
    """A writers entry as the agreement names it: its function, without the module a position resolves to."""
    return writer.rpartition(':')[2]


def _writer_issue(change, owner, outside, where):
    """The `writer:` finding of one writers agreement: one member per function that writes the field outside it.
    The agreement is the current one, judged on the baseline code too (`Change.baseline_writes`, D2): a function is
    new (fresh) when it writes outside more often now than the baseline code did, so an agreement added over writes
    that were already there leaves them old."""
    from .health import Issue, LINES_ONLY
    now = {}
    for row in outside:
        now.setdefault(row_function(row), []).append(row)
    fresh = set()
    if change.baseline and change.baseline_paths():
        before = {}
        # The baseline's writes read once for every agreement (`writes_to` picks this one's field).
        for row in change.graph.writes_to(change.baseline_writes(by_name=True), owner.name):
            if not row.get('unclear') and not _allowed(row, owner.writers):
                before.setdefault(row_function(row), Counter())[_write_key(row)] += 1
        fresh = {function for function, rows in now.items()
                 if any(count > before.get(function, Counter())[key] for key, count in Counter(map(_write_key, rows)).items())}
    names = list(dict.fromkeys(map(_writer_name, owner.writers)))
    step = 'call ' + ' or '.join(names) + ' instead'
    what = f'writes {owner.name} outside ' + ', '.join(names)
    parts = tuple((function, place(rows[0]), what, step) for function, rows in sorted(now.items()))
    return Issue(f'writer:{owner.name}', LINES_ONLY, f'writer {owner.name}',
                 f'{owner.name} is written outside its writers agreement ({where}): ' + '  '.join(place(rows[0]) for _, rows in sorted(now.items())),
                 step, frozenset(now), frozenset(row['file'] for row in outside),
                 family='writer', subject=f'writers {owner.name}', parts=parts, fresh=frozenset(fresh),
                 detail=(f'agreement: {where}', 'if the owner agrees that a function may write it, add it to that writers agreement'))


def _call_tree(graph, node, depth=3, up=0, *, fold=named):
    """{function: how}: the function and what it calls, down `depth` levels (first `up` levels of callers, with
    `up`), each id folded by `fold` (`named`: a callback is its function's); JS/TS member calls are resolved by
    name ('name'). With `fold=_member` a module-level callback keeps its own id, and one that calls into the climb
    (which `graph.call_tree` reaches as its bare module, since it climbs to named functions) is a caller too, with
    what it calls `depth` levels down."""
    tree = {}
    def add(found, via='edge'):
        for ident, how in found.items():
            key = fold(ident)
            how = 'name' if 'name' in (via, how) else how
            tree[key] = 'name' if 'name' in (how, tree.get(key)) else how
    add(graph.call_tree(node, depth, up=up))
    if fold is _member and up:
        climbed = graph.call_tree(node, 0, up=up)
        _, upward = graph.call_index()
        for ident, how in climbed.items():
            for caller, edge in upward.get(ident, {}).items():
                key = _member(caller)
                if key != named(caller) and named(caller) in climbed and key not in tree:
                    add(graph.call_tree(key, depth), 'name' if 'name' in (how, edge) else 'edge')
    return tree


OPERATION = 'the same operation (3 caller levels, then 3 callee levels)'


def operation(graph, node, *, fold=named):
    """{named function: how} of the operation a function belongs to: its callers three levels up and what
    each of them calls three levels down, so a caller that writes one field through one helper and its
    partner through another is one operation. Pairs and deletes read the same tree; pairs name a module-level
    callback by itself (`fold=_member`)."""
    return _call_tree(graph, node, 3, up=3, fold=fold)


def creates(row):
    """Does a write row make a row (create, createMany, upsert's create branch, a nested create, SQL INSERT) rather
    than change one that exists?"""
    from .health import INSERTING
    return row['kind'] in INSERTING or row['kind'].startswith(('nested:create', 'nested:upsert:create', 'nested:connectOrCreate'))


def _holds(row, value):
    if value is None:
        return True
    values = row.get('values') or ([row['value']] if 'value' in row else [])
    return any(str(item) == value for item in values)


def _pair_function(row):
    """The member a write row is of in a pair: `row_function(row)`, or the module-level callback that holds a JS/TS
    write (`_member`)."""
    if row.get('language', 'python') != 'python' and row['function'] == '<module>' and '<anonymous' in row['node']:
        return _member(row['node'])
    return row_function(row)


def _same_call(a, b):
    return (a['file'], a['node'], a.get('call_line')) == (b['file'], b['node'], b.get('call_line'))


def _same_record(trigger, partner):
    """(holds, why not confirmed): may a partner write of the trigger's own function write the trigger's record (D20)?
    Yes in the same call. A create of the trigger's own model makes another record than the one the trigger's `where`
    selects, so it does not hold such a trigger. Otherwise yes when either call has no `where` (it makes a row); a
    `where` that cannot be read counts, not confirmed; else one model must select by the same text (another `id` is
    another record) and two models by different text (the same `{ id }` on two models names unrelated records)."""
    if _same_call(trigger, partner):
        return True, ''
    if 'selector' in trigger and 'selector' not in partner and creates(partner) \
            and trigger.get('accessor') == partner.get('accessor'):
        return False, ''
    if 'selector' not in trigger or 'selector' not in partner:
        return True, ''
    if trigger['selector'] is None or partner['selector'] is None:
        return True, 'its where cannot be read'
    return (trigger['selector'] == partner['selector']) == (trigger.get('accessor') == partner.get('accessor')), ''


def _exclusive(marks, others):
    """Do two lists of condition marks (`ecma.object_fields`: position and branch) put their writes in two branches of
    one conditional expression?"""
    branch = {mark[:-1]: mark[-1] for mark in marks}
    return any(branch.get(mark[:-1], mark[-1]) != mark[-1] for mark in others)


def _unconditional(trigger, partner):
    """(holds, why not confirmed) for a partner field the reader marks `conditional` (a spread or a branch of
    `c && {...}`, `c ? {...} : {...}`, `a || {...}`), D21: it holds the pair in the trigger's own call under the
    trigger's own conditions, never from the other branch of a conditional the trigger is written in; a trigger
    written always is not held by it; when the trigger is written under a condition too, the two conditions are not
    compared (a variable may tie them) and it counts, not confirmed."""
    marks = partner.get('conditional')
    if not marks:
        return True, ''
    if _same_call(trigger, partner):
        if _exclusive(trigger.get('conditional') or (), marks):
            return False, ''
        if set(marks) <= set(trigger.get('conditional') or ()):
            return True, ''
    return (True, 'it is written under another condition') if trigger.get('conditional') else (False, '')


def _held(trigger, function, tree, partners):
    """(held, (unconfirmed partner, why) or None): does a partner write [(row, member)] of the operation `tree` hold
    the trigger write of `function`? A partner of the same function must write the same record (`_same_record`),
    and a conditional partner field must be written whenever the trigger is (`_unconditional`)."""
    unconfirmed = None
    for partner, member in partners:
        if member not in tree:
            continue
        holds, why = _unconditional(trigger, partner)
        if holds and member == function:
            holds, record = _same_record(trigger, partner)
            why = why or record
        if holds and not why:
            return True, None
        if holds and unconfirmed is None:
            unconfirmed = (partner, why)
    return unconfirmed is not None, unconfirmed


class _Calls:
    """The baseline side of a pair: whom a baseline write row is of (`current`), and the callee-stability guard (`exact`).

    The baseline result is read with the current operation tree, which is exact for what a change adds (a larger tree
    only holds more) but not for what it takes away: a member missing its partner now may have been held at the
    baseline through a call that is gone. So a member is judged at the baseline only while its tree lost nothing;
    otherwise it counts as new (fail-closed red). The tree lost something when, at the baseline,

    - a function on it, in a file this change alters, called what it no longer calls, or a name its file now imports
      from elsewhere;
    - a function on it called a function this change removes;
    - code of a changed file (a function, a module-level callback, JS/TS module code) called the member or one of its
      callers up to two levels up, and no longer does.

    A call counts only where it may reach a function of the project as the map resolves calls (`reaches`). Test files
    take no part, as in the operation tree. A module-level callback has no stable id (its id says where it starts):
    its baseline counterpart is the callback of the same file with the same code and registration, or else the one
    registered so once on each side (`callbacks`). Not seen: an unchanged call whose target a changed file redirects
    by a re-export, or makes ambiguous by adding a function of the same name. Read once per change."""

    def __init__(self, change):
        self.change = change
        self._maps, self._groups, self._bindings, self._external, self._index = {}, {}, {}, {}, {}
        self._python, self._modules = {}, {}
        self._production = self._tests = self._targets = self._removed = self._defaults = self._by_id = None
        self._lost = self._by_name = None

    def python(self, file):
        """Is `file` Python (else JS/TS: calls never cross the two)?"""
        if file not in self._python:
            from flowguard.structure.readers.registry import language_for
            self._python[file] = language_for(file) == 'python'
        return self._python[file]

    def tests(self):
        """The map's test files."""
        if self._tests is None:
            self._tests = {path for (path,) in self.change.graph.con.execute('SELECT path FROM file WHERE is_test = 1')}
        return self._tests

    def production(self):
        """The paths of `baseline_paths` a reader reads, test files left out."""
        if self._production is None:
            from flowguard.structure.readers.registry import language_for
            self._production = frozenset(path for path in self.change.baseline_paths() if language_for(path)
                                         and self.change.module(path) and path not in self.tests() and not is_test_file(path))
        return self._production

    # ---- module-level callbacks: the same one at the baseline and now ----------------------------------------

    def callbacks(self, file):
        """(baseline id -> current id, current id -> baseline id) of the module-level callbacks of a changed file. A
        baseline callback whose code (fingerprint) a current one has, registered the same way (`ecma.registration`,
        its `#n` aside), is that one, in file order; of the rest, a registration left once on each side pairs them.
        Any other callback is new, or gone."""
        if file not in self._maps:
            import re
            from flowguard.structure import store
            def listed(rows):
                return [(ident, re.sub(r'#\d+$', '', raw.get('callback') or ''), fp)
                        for ident, qual, fp, raw in rows if qual.startswith('<anonymous') and '.' not in qual]
            module = self.change.module(file)
            old = listed((f'{module}:{row["qual"]}', row['qual'], row['fp'], row.get('raw') or {})
                         for row in self.change.old_part(file, 'nodes') or ())
            now = listed((ident, qual, fp, store.unpack(raw) if raw else {}) for ident, qual, fp, raw in self.change.graph.con.execute(
                "SELECT id, qual, fp, raw FROM node WHERE file=? AND qual LIKE '<anonymous%' ORDER BY line", (file,)))
            forward, waiting = {}, {}
            for ident, label, fp in now:
                waiting.setdefault((label, fp), []).append(ident)
            for ident, label, fp in old:
                if waiting.get((label, fp)):
                    forward[ident] = waiting[(label, fp)].pop(0)
            taken = set(forward.values())
            rest_old = [(ident, label) for ident, label, _ in old if ident not in forward]
            rest_now = [(ident, label) for ident, label, _ in now if ident not in taken]
            left, right = Counter(label for _, label in rest_old), Counter(label for _, label in rest_now)
            for ident, label in rest_old:
                if label and left[label] == right[label] == 1:
                    forward[ident] = next(new for new, other in rest_now if other == label)
            self._maps[file] = forward, {new: ident for ident, new in forward.items()}
        return self._maps[file]

    def current(self, row):
        """The member a baseline write row is of, named as the current map names it (`_pair_function`): a module-level
        callback of a changed file by its counterpart (`callbacks`), or by an id no current function has."""
        function = _pair_function(row)
        if function == row_function(row) or row['file'] not in self.change.baseline_paths():
            return function
        return self.callbacks(row['file'])[0].get(function, function + ' (at the baseline)')

    # ---- what each caller of a file calls, and through which binding ----------------------------------------

    def module(self, file):
        """`Change.module(file)`, read once per file."""
        if file not in self._modules:
            self._modules[file] = self.change.module(file)
        return self._modules[file]

    def groups(self, file, *, old=False):
        """{key: names}: what the callers of one file call now or (`old`) at the baseline (`Change.calls`). The key is
        ('fn', id) for a named function, what its nested callbacks call folded in; ('cb', current id) for a module-level
        callback, a baseline one by its counterpart and ('gone', baseline id) without one; ('module', module) for JS/TS
        module code, which calls as a caller does (Python module code is no caller on the operation tree)."""
        if (file, old) not in self._groups:
            forward = self.callbacks(file)[0] if old else None
            found = {}
            for node, names in self.change.calls(file, old=old).items():
                module, _, qual = node.partition(':')
                if not qual:
                    if self.python(file):
                        continue
                    key = ('module', module)
                elif named(node).partition(':')[2]:
                    key = ('fn', named(node))
                elif forward is None:
                    key = ('cb', _member(node))
                else:
                    key = ('cb', forward[_member(node)]) if _member(node) in forward else ('gone', _member(node))
                found.setdefault(key, set()).update(names)
            self._groups[(file, old)] = found
        return self._groups[(file, old)]

    def of(self, file, ident, *, old=False):
        """[(key, names)] of `groups(file, old=)` that belong to the function `ident` of an operation tree: a named
        function with what it nests, a module-level callback, or (a bare module) its module code."""
        index = self._index.setdefault((file, old), {})
        if not index:
            index[None] = []
            for key, names in self.groups(file, old=old).items():
                if key[0] == 'fn':
                    module, _, qual = key[1].partition(':')
                    parts = qual.split('.')
                    for depth in range(1, len(parts) + 1):
                        index.setdefault(f'{module}:{".".join(parts[:depth])}', []).append((key, names))
                elif key[0] in ('cb', 'module'):
                    index.setdefault(key[1], []).append((key, names))
        return index.get(ident, [])

    def binding(self, file, key, name, *, old=False):
        """What binds the first name `name` of a call of the caller `key` of `file` now or at the baseline: a JS/TS
        import (the module as spelled, the name it imports), a Python import (`module:name` or `module`; a function's
        own import first); None when no import does."""
        if (file, old) not in self._bindings:
            facts = self.change.facts(file, old=old) or {}
            if facts.get('language') == 'python':
                data = facts.get('facts') or {}
                module = self.change.module(file) if old else self.change._modules.get(file)
                self._bindings[(file, old)] = dict(data.get('imports') or {}), {
                    f'{module}:{qual}': function.get('local_imports') or {} for qual, function in (data.get('functions') or {}).items()}
            else:
                self._bindings[(file, old)] = {row['alias']: (row['module'], row.get('name')) for row in facts.get('dependencies', ())
                                               if row.get('kind') == 'import' and row.get('alias')}, {}
        top, local = self._bindings[(file, old)]
        ident = key[1] if key[0] == 'fn' else ''
        while ident.partition(':')[2]:
            if name in local.get(ident, {}):
                return local[ident][name]
            module, _, qual = ident.partition(':')
            ident = f'{module}:{qual.rpartition(".")[0]}'
        return top.get(name)

    def lost(self):
        """{key: [(file, name, baseline binding)]}: per caller of the files this change alters (`production`), each
        name it called at the baseline and no longer calls, or now calls through another binding (an import from
        elsewhere)."""
        if self._lost is None:
            self._lost = {}
            for file in sorted(self.production()):
                now = self.groups(file)
                for key, names in self.groups(file, old=True).items():
                    for name in sorted(names):
                        head = name.split('.')[0]
                        then = self.binding(file, key, head, old=True)
                        if name not in now.get(key, ()) or then != self.binding(file, key, head):
                            self._lost.setdefault(key, []).append((file, name, then))
        return self._lost

    # ---- the functions a call may reach ------------------------------------------------------------------------

    def targets(self):
        """{(Python?, name): [target]}: the functions a call may reach, by language and the name a call ends in; a
        target is (id, file, qual, holder): each named function and method of the map outside test files, and each one
        this change removes (`removed`: of a production file it alters, at the baseline and no longer on the map)."""
        if self._targets is None:
            from flowguard.structure import store
            found, ids = {}, set()
            self._by_id = {}
            def add(ident, file, qual, data):
                target = (ident, file, qual, data.get('holder') or (qual.rpartition('.')[0] if '.' in qual else ''))
                name = data.get('name') or qual.rpartition('.')[2].split('@')[0]
                found.setdefault((self.python(file), name), []).append(target)
                self._by_id[ident] = name, target
                return target
            for ident, file, qual, raw in self.change.graph.con.execute(
                    "SELECT id, file, qual, raw FROM node WHERE kind IN ('function', 'method')"):
                ids.add(ident)
                if file and '<anonymous' not in qual and file not in self.tests() and not is_test_file(file):
                    add(ident, file, qual, store.unpack(raw) if raw and not self.python(file) else {})
            self._removed = []
            for file in sorted(self.production()):
                module = self.change.module(file)
                for row in self.change.old_part(file, 'nodes') or ():
                    ident = f'{module}:{row["qual"]}'
                    if row['kind'] in ('function', 'method') and '<anonymous' not in row['qual'] and ident not in ids:
                        self._removed.append(add(ident, file, row['qual'], row.get('raw') or {}))
            self._targets = found
        return self._targets

    def removed(self):
        """The targets this change removes (`targets`)."""
        self.targets()
        return self._removed

    def defaults(self):
        """The targets each file exports as its default, which a default import calls by another name."""
        if self._defaults is None:
            exported = {path: data['exports'].get('default') for path, _, data in self.change.graph._kinds('exports')
                        if data.get('exports')}
            self._defaults = {target for (python, _), targets in self.targets().items() if not python for target in targets
                              if exported.get(target[1]) == target[2]}
        return self._defaults

    def candidates(self, file, name, binding, among=None):
        """The targets a call `name` of `file` with this binding of its first name may reach by name: those of its
        language its last name names, or, through a JS/TS default import, those exported as a default. `among`
        narrows them."""
        if isinstance(binding, tuple) and binding[1] == 'default' and '.' not in name:
            found = self.defaults()
        else:
            found = self.targets().get((self.python(file), name.rpartition('.')[2]), ())
        return [target for target in found if among is None or target in among]

    def _ecma_external(self, file, module):
        """Is the JS/TS import of `module` (as spelled) in `file` one of a package outside the project: not relative,
        and the map resolves the file's current imports of it nowhere? False for one the file no longer has."""
        if (file, module) not in self._external:
            rows = [row for row in (self.change.facts(file) or {}).get('dependencies', ()) if row.get('module') == module]
            self._external[(file, module)] = bool(rows) and not module.startswith(('.', '/')) \
                and all(row.get('resolved') is None for row in rows)
        return self._external[(file, module)]

    def reaches(self, name, file, binding, target):
        """May the call `name` (as spelled) of `file`, its first name bound by `binding`, reach the function `target`
        (one of `candidates`) as the map resolves calls? JS/TS (the import links and `MapHandle.call_index`): through
        the import that binds its first name, when that imports the target or its holder (a namespace or a default
        import: any), never into a package outside the project; else by name within the target's package, a
        `holder.name` call only to that holder's function when a function of the project has that holder; a Prisma
        client call never. Python (the store's links): through the import, into its module or below; else a plain
        name into the caller's own module, an attribute call anywhere."""
        from flowguard.structure.readers.ecma import PRISMA_READS, PRISMA_WRITES
        ident, place, qual, holder = target
        parts = name.split('.')
        if self.python(file) != self.python(place):
            return False
        if self.python(file):
            module = ident.partition(':')[0]
            if binding is not None:
                bound = binding.partition(':')[0]
                return module in (bound, binding.replace(':', '.')) or module.startswith(bound + '.')
            return len(parts) > 1 or self.module(file) == module
        if len(parts) >= 3 and parts[-1] in PRISMA_WRITES | PRISMA_READS:
            return False
        if binding is not None:
            module, imported = binding
            return not self._ecma_external(file, module) and (imported in ('*', 'default', None, holder)
                                                              or imported == qual.split('.')[0].split('@')[0])
        if self.change.graph.package(file) != self.change.graph.package(place):
            return False
        receiver = parts[-2] if len(parts) > 1 else ''
        return receiver in ('', 'this') or holder == receiver \
            or not any(other[3] == receiver for other in self.targets().get((False, parts[-1]), ()))

    def _reached(self, file, name, binding, among=None):
        return next((target[0] for target in self.candidates(file, name, binding, among)
                     if self.reaches(name, file, binding, target)), None)

    # ---- the guard -----------------------------------------------------------------------------------------------

    def exact(self, tree, function):
        """(exact, why): may the member `function` be judged at the baseline with its current operation `tree`? Not
        when the tree lost a call (see the class)."""
        change, lost, removed = self.change, self.lost(), set(self.removed())
        for ident in tree:
            file = change.path_of(ident.partition(':')[0])
            if file is None or file in self.tests() or is_test_file(file):
                continue
            changed = file in change.baseline_paths()
            if file in self.production():
                for key, _ in self.of(file, ident, old=True):
                    for place, name, binding in lost.get(key, ()):
                        if (reached := self._reached(place, name, binding)) is not None:
                            return False, f'{ident} no longer calls {name} as it did at the baseline ({reached})'
            if removed:
                for key, names in self.of(file, ident, old=changed):
                    for name in sorted(names):
                        binding = self.binding(file, key, name.split('.')[0], old=changed)
                        if (reached := self._reached(file, name, binding, removed)) is not None:
                            return False, f'{ident} calls {reached}, which this change removes'
        if self._by_name is None:
            self._by_name = {}                    # the lost calls by the name they end in; a default import's by None
            for items in lost.values():
                for place, name, binding in items:
                    default = isinstance(binding, tuple) and binding[1] == 'default' and '.' not in name
                    self._by_name.setdefault(None if default else (self.python(place), name.rpartition('.')[2]), []).append(
                        (place, name, binding))
        for ident in change.graph.call_tree(function, 0, up=2):
            if ident not in self._by_id:          # a callback, module code or a test: no call reaches it by name
                continue
            name, target = self._by_id[ident]
            calls = self._by_name.get((self.python(target[1]), name), [])
            calls = calls + (self._by_name.get(None, []) if target in self.defaults() else [])
            for place, spelled, binding in calls:
                if self.reaches(spelled, place, binding, target):
                    return False, f'{place} no longer calls {ident} ({spelled})'
        return True, ''


class _TargetWrites:
    """The rows of `rows` (write rows) that write a target (`_writes_target`), in their order, each target's kept: only
    the rows that name the target's model, table, field or column (`_write_names`) are judged, as no other row can
    write it."""

    def __init__(self, rows, models):
        from flowguard.structure.api import _write_names
        self.rows, self.models, self.named, self.held = rows, models, {}, {}
        for at, row in enumerate(rows):
            names, fields = _write_names(row)
            for name in names | fields:
                self.named.setdefault(name, []).append(at)

    def __call__(self, target):
        from flowguard.structure.api import _writes_target
        if target not in self.held:
            head, dot, tail = target.rpartition('.')
            near = set(self.named.get(head.casefold(), ())) | set(self.named.get(tail.casefold(), ())) if dot \
                else self.named.get(tail.casefold(), ())
            self.held[target] = [self.rows[at] for at in sorted(near) if _writes_target(self.rows[at], target, self.models)]
        return self.held[target]


def _pair_place(row):
    """'path:symbol' of a write's function; 'path:line' for a module-level write or callback."""
    return f'{row["file"]}:{row["function"] if row["function"] != "<module>" else row["line"]}'


def _pair_step(row, partner):
    if row['function'] != '<module>':
        return f'also write {partner} in {row["function"].rpartition(".")[2]}'
    return f'also write {partner} in the callback of {row["callback"]}' if row.get('callback') else \
        f'also write {partner} in the code at line {row["line"]}'


def owner_pairs(change, index):
    """`together A B`: each write of a registered field also writes its partner in the same operation
    (`operation`: callers three levels up, then three levels down from them; a JS/TS module-level callback is an
    operation of its own), unless its function is listed in `except=` (`alone`); `on=update` holds only the writes that change
    a row (`on=create` only those that make one, `creates`). A partner of the trigger's own function holds it only
    for the same record (`_same_record`), and a conditional partner field only under the trigger's own condition
    (`_unconditional`). A test's fixture write is not held to the pair.

    One `pair:A>B` finding per agreement and partner, one part per function that misses it (`_pair_function`).
    A part is fresh (this change added it) unless the baseline result has it: the current registration applied to
    the baseline code (the writes of every changed file at the baseline, `Change.baseline_writes`, a module-level
    callback by its counterpart), judged with the current operation tree, and only while that tree lost no call the
    baseline had (`_Calls`; else the part is fresh, fail-closed). Without a baseline nothing is fresh.

    The finding's detail notes a hold that counts but is not confirmed (a `where` that cannot be read, D20; two
    conditions not compared, D21) for each function that has one; an agreement whose every trigger is held has no
    finding, so such a note shows only beside a member that misses its partner."""
    from .health import Issue
    found = Findings()
    def bound(row):         # a JS/TS `obj.f = ...` matched by field name alone is not a write of a model
        return not row.get('unclear') and not (row.get('how') == 'name' and row.get('language', 'python') != 'python')
    tests = {path for (path,) in change.graph.con.execute('SELECT path FROM file WHERE is_test = 1')}
    trees, guard, every = {}, _Calls(change), {}
    def writes(target, *, old=False):
        """`graph.writes(target, by_name=True)` (`old`: `Change.baseline_writes`), every row read once per side."""
        if old not in every:
            every[old] = _TargetWrites(change.baseline_writes(by_name=True), change.baseline_definitions().models
                                       if change.baseline_paths() else change.graph._models()) if old else \
                _TargetWrites(change.graph.writes(by_name=True), change.graph._models())
        return every[old](target)
    def tree_of(function):
        if function not in trees:
            trees[function] = operation(change.graph, function, fold=_member)
        return trees[function]
    for owner in (a for a in index.entries if a.kind == 'owner' and a.pairs):
        alone = [item.partition('(')[0] for item in owner.alone]
        def triggers(written):
            return [row for row in written if bound(row) and row['file'] not in tests and not is_test_file(row['file'])
                    and (not owner.on or creates(row) == (owner.on == 'create')) and not _allowed(row, alone)]
        rows = triggers(writes(owner.name))
        for pair in owner.pairs:
            target, _, value = pair.partition('=')
            model, _, column = target.rpartition('.')
            written = model if column == '*' else target
            def partners(rows):
                return [row for row in rows if bound(row) and _holds(row, value or None)]
            now = [(row, _pair_function(row)) for row in partners(writes(written))]
            missing, calls, members, unconfirmed = [], {}, {}, {}
            for row in rows:
                function = _pair_function(row)
                tree = tree_of(function)
                held, unsure = _held(row, function, tree, now)
                if not held:
                    missing.append(row)
                    members.setdefault(function, row)
                    calls[id(row)] = 'name' in tree.values() or row.get('language', 'python') != 'python'
                elif unsure is not None:
                    unconfirmed.setdefault(function, (row, unsure))
            def where(rows):
                return '  '.join(f'{row["file"]}:{row["line"]} {row["function"]}' for row in rows) \
                    + ('(JS/TS calls resolved by name)' if any(calls[id(row)] for row in rows) else '') \
                    + {'update': '(updates only)', 'create': '(creates only)'}.get(owner.on, '')
            step = (f'write the paired value; an except=path:function(reason) on the together agreement (comment at '
                    f'{_agreement_place(change.graph, owner, "pairs")}) would loosen it, which is the owner\'s decision')
            if not missing:
                continue
            fresh, detail = set(), []
            if change.baseline:
                then = triggers(writes(owner.name, old=True))
                then_partners = [(row, guard.current(row)) for row in partners(writes(written, old=True))]
                for function, row in members.items():
                    old = [item for item in then if guard.current(item) == function]
                    if not old or all(_held(item, function, tree_of(function), then_partners)[0] for item in old):
                        fresh.add(function)
                        continue
                    exact, why = guard.exact(tree_of(function), function)
                    if not exact:
                        fresh.add(function)
                        detail.append(f'{_pair_place(row)} counts as new: {why}, so its baseline cannot be read')
            partner = model if column == '*' else pair
            scope = {'update': ' (updates only)', 'create': ' (creates only)'}.get(owner.on, '')
            detail += [f'{_pair_place(row)}: {_pair_place(unsure)} writes {pair}, but {why}: not confirmed'
                       for row, (unsure, why) in unconfirmed.values()]
            if any(calls.values()):
                detail.append('JS/TS calls resolved by name')
            found.issues.append(Issue(
                f'pair:{owner.name}>{pair}', 2, f'pair {owner.name}',
                f'missing paired write: {where(missing)} writes {owner.name}; {OPERATION} does not write {pair}',
                step, frozenset(row_function(row) for row in missing), frozenset(row['file'] for row in missing),
                family='pair', subject=f'together {owner.name}',
                parts=tuple((function, _pair_place(row), f'writes {owner.name} without {pair}{scope}', _pair_step(row, partner))
                            for function, row in members.items()),
                fresh=frozenset(fresh), detail=tuple(detail)))
    return found


# ---- declarations of one name that differ -------------------------------------------------------------

def _declarations(graph):
    """Named value sets the map reads: union type aliases (`type X = 'a' | 'b'`, `X = Literal[...]`) and
    Python enums; {name: [(file, line, values)]}."""
    from flowguard.structure import decide
    from . import anchors
    from flowguard.structure.readers.registry import ECMA, language_for
    found, sets = {}, {}
    for row in graph.declarations():          # JS/TS: unions, `as const` arrays and objects, `new Set`, aliases
        found.setdefault(row['name'], []).append((row['file'], row['line'], frozenset(row['values'])))
    for row in graph.literals(contexts={'union'}):
        if row.get('declaration') and language_for(row['file']) not in ECMA:
            item = sets.setdefault((row['declaration'], row['file']), [row['line'], set()])
            item[0] = min(item[0], row['line'])
            item[1].add(row['value'])
    for (name, file), (line, values) in sets.items():
        found.setdefault(name, []).append((file, line, frozenset(values)))
    for ident, file, line, sig in graph.con.execute("SELECT id, file, line, sig FROM node WHERE kind = 'class' AND file LIKE '%.py'"):
        if {base.rpartition('.')[2] for base in decide.class_bases(sig or '')} & anchors._ENUM_BASES:
            module, _, cls = ident.partition(':')
            values = frozenset(folded[1] for key, folded in graph._value_env(module).items() if key.startswith(cls + '.')
                               and '.' not in key[len(cls) + 1:] and folded and folded[0] in ('str', 'num'))
            if values:
                found.setdefault(cls.rpartition('.')[2], []).append((file, line, values))
    return found


def declarations_differ(change):
    """Two declarations of one name (union type or enum) with different members, and the declarations of one
    database field (`MapHandle.field_declarations`: each Prisma schema's enum, each SQL CHECK, a JS/TS
    declaration of the enum's name) with different values: a `declarations:` finding of the files declaring it, new
    when a file declares that name otherwise than the baseline code did (`_declared`)."""
    found = Findings()
    found.ran.add('declarations')
    named = [(name, items, ' -> keep one definition and reference it elsewhere; use different names if intentionally different') for name, items in _declarations(change.graph).items()]
    fields = [(name, items, ' -> add missing values; mark an unused description or remove it') for name, items in change.graph.field_declarations().items()]
    field_names = {name for name, _, _ in fields}
    for name, items, step in sorted(named + fields):
        if len(items) < 2 or len({values for _, _, values in items}) < 2:
            continue
        found.issues.append(_declarations_issue(change, name, items, step.removeprefix(' -> '), field=name in field_names))
    return found


def _declarations_issue(change, name, items, step, *, field=False):
    from .health import Issue, LINES_ONLY
    ordered = sorted(items)
    def declared(values):
        return ' | '.join(map(repr, sorted(values, key=repr)))
    (first, line, values), rest = ordered[0], ordered[1:]
    what = f'declares {declared(values)}; ' + '; '.join(f'{file}:{at} declares {declared(other)}' for file, at, other in rest)
    files = frozenset(file for file, _, _ in items)
    fresh = bool(change.baseline) and bool(change.baseline_paths()) and any(
        _declared(change, name, file, field=field, then=True) != _declared(change, name, file, field=field, then=False)
        for file in sorted(files))
    return Issue(f'declarations:{name}', LINES_ONLY, f'declarations {name}', f'declarations differ: {name}: {first}:{line} {what}',
                 step, frozenset(), files, family='declarations', subject=f'declarations {name}',
                 parts=(('', f'{first}:{line}', what, step),), fresh=frozenset({''}) if fresh else frozenset())


def _declared(change, name, file, *, field, then):
    """What `file` declares for the declarations finding `name`, positions aside, as the code stands now or (`then`)
    stood at the baseline (its baseline bytes, and the baseline's sets, constants and models: an alias or an enum
    member resolves as it did then): for a set name (`_declarations`), its exported JS/TS sets (an alias with the
    values it names), its Python `Literal` union members and the member values of its Python enums; for a
    database field `Model.field` (`MapHandle.field_declarations`), the type the file's Prisma models give the
    field and the members of the Prisma enums typing it, its CHECK values on the field's column and the exported
    JS/TS sets named like those enums. Only the name's own declarations count: a set, a model or a CHECK added
    beside them leaves the finding as old as it was. Read once per file, name and side."""
    def held():
        from flowguard.structure import decide
        from . import anchors
        graph = change.graph
        definitions = change.baseline_definitions() if then else None
        sets = definitions.sets if then else graph._ts_sets()
        models = definitions.models if then else graph._models()
        old = then and file in change.baseline_paths()          # else the file's code is the map's on both sides
        facts = change.old_facts(file) if old else change.held(('facts now', file), lambda: graph.file_facts(file) or {})

        def ts(names):
            out = []
            for row in facts.get('value_sets') or ():
                if row['name'] in names and row.get('exported'):
                    values = sorted({repr(tuple(other['values'])) for other in sets.get(row['of'], ()) if other['kind'] != 'alias'}) \
                        if row['kind'] == 'alias' else repr(tuple(row['values']))
                    out.append(('ts', row['name'], row['kind'], repr(values)))
            return out
        if field:
            model, _, column = name.partition('.')
            enums = {item['type'] for description in models.by_name.get(model, ()) for item in description['fields']
                     if item['name'] == column}
            schema = facts.get('schema') or {}
            out = ts(enums)
            if schema.get('kind') == 'prisma':
                out += [('type', item['type']) for block in schema.get('models', ()) if block['name'] == model
                        for item in block['fields'] if item['name'] == column]
                out += [('enum', block['name'], tuple(member['name'] for member in block['fields']))
                        for block in schema.get('enums', ()) if block['name'] in enums]
            elif schema.get('kind') == 'sql':
                for item in [*schema.get('tables', ()), *schema.get('changes', ())]:
                    table = item.get('name') or item['table']
                    for check in item.get('checks', ()):
                        found = models.column_field(model, check['column']) if models.table_model(table) == model else None
                        if found is not None and found['name'] == column:
                            out.append(('check', table.casefold(), check['column'].casefold(), tuple(check['values'])))
            return sorted(out)
        out = ts({name})
        out += [('union', repr(value)) for value in sorted({repr(row['value']) for row in facts.get('literals') or ()
                                                            if row.get('context') == 'union' and row.get('declaration') == name})]
        module = change.module(file)
        classes = [(node['qual'], node.get('sig')) for node in facts.get('nodes', ()) if node['kind'] == 'class'] if old \
            else [(qual, sig) for qual, sig in graph.con.execute("SELECT qual, sig FROM node WHERE file = ? AND kind = 'class'", (file,))]
        env = (definitions.env(module) if then else graph._value_env(module)) if module and classes else {}
        for qual, sig in classes:
            if qual.rpartition('.')[2] == name and {base.rpartition('.')[2] for base in decide.class_bases(sig or '')} & anchors._ENUM_BASES:
                out.append(('enum', tuple(sorted(repr(folded[1]) for key, folded in env.items() if key.startswith(qual + '.')
                                                 and '.' not in key[len(qual) + 1:] and folded and folded[0] in ('str', 'num')))))
        return sorted(out)
    return change.held(('declared', name, file, field, then), held)


def _counted(number, noun, plural=None):
    """`1 reader`, `2 readers`, `1 copy`, `3 copies`: a count with its noun in the number it needs."""
    return f'{number} ' + (noun if number == 1 else plural or noun + 's')


# ---- what this change loosened, and the fields it newly writes (4.3) ----------------------------------


def _agreements(rows, modules, moved=None):
    """The agreements of these `anchors` fact rows: {field: {'writers': {writer: row}, 'pairs': {partner: row},
    'alone': {function: row}, 'on': {on: row}}} of the data agreements (writers, together), and {(name, function):
    [rows]} of the same-name copies (`same`, `same NAME ref`). A position is the function it resolves to
    (`module:function`; a Python position in another file keeps its path, which `modules`, {path: module}, maps), so
    a comment moved to another file means the function of that file it now names; `moved` maps the module of a file
    renamed away to its new module."""
    moved = moved or {}

    def resolved(position):
        target, _, qual = position.rpartition(':')
        target = modules.get(target, target)
        return moved.get(target, target) + ':' + qual
    data, same = {}, {}
    for row in rows:
        if row['kind'] == 'owner' and not row.get('qual'):
            item = data.setdefault(row['name'], dict(writers={}, pairs={}, alone={}, on={}))
            for writer in row.get('writers', ()):
                item['writers'].setdefault(resolved(writer), row)
            for partner in row.get('pairs', ()):
                item['pairs'].setdefault(partner, row)
            for exception in row.get('alone', ()):
                item['alone'].setdefault(resolved(exception.partition('(')[0]), row)
            if row.get('pairs'):
                item['on'].setdefault(row.get('on') or '', row)
        elif row['kind'] == 'sensor':
            same.setdefault((row['name'], resolved(row['module'] + ':' + row['qual'])), []).append(row)
    return data, same


def _moved_modules(change, paths, current, before):
    """{old module: new module} of the files this change renames: those Git reports renamed (`Change.renamed`, a
    staged rename), and a file deleted beside one added whose comments (`current`, {path: rows}) are the baseline
    file's (`before`, {path: rows} of `paths` at the baseline), up to the file and module they name (a file moved
    without Git, its comments with it). The rows are a file's `anchors` facts and its removed 4.2 comments as written
    (`_stated`)."""
    moved = {change.module(old): change._modules[new] for old, new in change.renamed().items()
             if new in change._modules and change.module(old)}

    def shape(rows, module):
        def own(value):
            return value.replace(module + ':', '<own>:') if isinstance(value, str) else \
                tuple(own(part) for part in value) if isinstance(value, (list, tuple)) else value
        return repr(sorted(repr(sorted((key, own(value)) for key, value in row.items()
                                       if key not in ('file', 'module', 'line', 'target_line', 'source_digest')))
                           for row in rows))
    gone = {}
    for path in sorted(paths):
        module = change.module(path)
        if path not in change._modules and module and module not in moved and (rows := before[path]):
            gone.setdefault(shape(rows, module), []).append(module)
    added = {}
    for path in sorted(change.files - set(change.renamed().values())):
        if current.get(path) and change.old_text(path) is None:
            added.setdefault(shape(current[path], change._modules[path]), []).append(change._modules[path])
    for key, modules in gone.items():
        if len(modules) == 1 and len(added.get(key, ())) == 1:
            moved[modules[0]] = added[key][0]
    return moved


def _stated(locate, path, module, issues, read):
    """(rows, comments) of one file's removed 4.2 comments: the `anchors` rows their steps state (`anchors.stated`),
    each step read again with the whole map's functions (`locate`, as `anchors.collect` reads it:
    `anchors._relocated`), and each comment as written ({'removed': text}, which names no file: a file moved without
    Git compares by them, `_moved_modules`). `issues` are the file's `anchor_issues` facts; `read()` gives its text and
    its reader's node rows, read only when it holds a removed comment."""
    from .anchors import _REMOVED_HEAD, Issue, _lines, _relocated, stated
    removed = [Issue(**value) for value in issues if value['code'] == 'removed']
    if not removed:
        return [], []
    text, nodes = read()
    lines = _lines(text)
    head = _REMOVED_HEAD['#' if path.endswith('.py') else '//']
    written = [{'removed': found[0].strip()} for issue in removed if 0 < issue.line <= len(lines)
               and (found := head.search(lines[issue.line - 1]))]
    return stated([_relocated(issue, lines, module, locate) for issue in removed], text, path, module, functions=nodes,
                  is_test=is_test_file(path)), written


def loosened(change, index):
    """What this change loosened in the agreements of its `flowguard:` comments (D9), each a `loosened` line: an
    `except=` added, also in a new together; a together partner removed (the whole agreement too); an
    `on=` added to or changed in a together that stays; a writer added to a writers agreement that stays; a writers
    agreement removed; a `same NAME` removed from a function. A 4.2 spelling binds no agreement in 5.0 (it is red at
    its line, `anchors._removed`); here alone, at the baseline and now, it compares as the agreement its red's step
    states (`_stated`), so a rewrite as that step says loosens nothing, while deleting the 4.2 line, or rewriting or
    editing it looser, is loosened as deleting or loosening its rewrite is. The baseline's comments are the old
    `anchors` and `anchor_issues` facts of the files this change edits, deletes or renames away, beside the map's for
    every other file. Positions compare
    as the functions they resolve to, a renamed file's by its new module (`_moved_modules`): a comment moved beside
    another function of the name it spells now names that function. A file moved without Git and edited in its
    comments too is a file deleted and one added."""
    from .signals import LOOSENED_STEP, Line
    found = Findings()
    paths = change.baseline_paths() if change.baseline else frozenset()
    if not paths:
        return found
    from flowguard.structure import store
    from .anchors import _graph_locator
    graph = change.graph
    # a 4.2 bare name means the functions of that name in the map, at the baseline too, as the step 5.0 prints names them
    modules = {path: change.module(path) for path in paths if change.module(path)} | change._modules
    locate = _graph_locator(graph, modules)

    def nodes(path):
        """The map's functions of a JS/TS file as its reader's node rows (`anchors.foreign_owners` reads them)."""
        return [dict(qual=qual, kind=kind, line=line, raw=store.unpack(raw) if raw else {})
                for qual, kind, line, raw in graph.con.execute("SELECT qual, kind, line, raw FROM node WHERE file = ? AND kind IN "
                                                               "('function', 'method') ORDER BY nid", (path,))]
    kinds = graph._kinds('anchors', 'anchor_issues')

    def stated_now(path, data):
        return _stated(locate, path, change._modules[path], data.get('anchor_issues', ()), lambda: (
            read_source(graph.root / path), () if path.endswith('.py') else nodes(path)))
    edited = {path: stated_now(path, data) for path, _, data in kinds if path in paths}
    current = {path: [*data.get('anchors', ()), *edited[path][1]] for path, _, data in kinds if path in paths}
    before, then_rows = {}, {}
    for path in sorted(paths):
        rows, written = _stated(locate, path, change.module(path), change.old_part(path, 'anchor_issues') or (),
                                lambda path=path: (read_source(graph.root / path, data=graph._baseline_bytes(change.baseline, path)),
                                                   () if path.endswith('.py') else change.old_part(path, 'nodes')))
        then_rows[path] = [*(change.old_part(path, 'anchors') or ()), *rows]
        before[path] = [*(change.old_part(path, 'anchors') or ()), *written]
    moved = _moved_modules(change, paths, current, before)
    # A file this change leaves alone states the same rows at the baseline and now: its 4.2 comments are read only when
    # they name a field or NAME a file it alters names too, or a renamed module could read them otherwise (`moved`).
    names = {row['name'] for rows in then_rows.values() for row in rows} | {
        row['name'] for path, _, data in kinds if path in paths for row in [*data.get('anchors', ()), *edited[path][0]]}
    old_rows, new_rows = [], []
    for path, _, data in kinds:
        if path in paths:
            rows = edited[path][0]
        elif moved or names.intersection(issue['name'] for issue in data.get('anchor_issues', ())
                                         if issue['code'] == 'removed'):
            rows = stated_now(path, data)[0]
        else:
            rows = []
        rows = [*data.get('anchors', ()), *rows]
        new_rows.extend(rows)
        if path not in paths:
            old_rows.extend(rows)
    for path in sorted(paths):
        old_rows.extend(then_rows[path])
    (then, same_then), (now, same_now) = _agreements(old_rows, modules, moved), _agreements(new_rows, modules)
    files = {module: path for path, module in modules.items()}

    def spelled(position, row):
        """A position as the comment at `row` spells it: a function of its own file bare, another's path:function."""
        target, _, qual = position.rpartition(':')
        return qual if target == row['module'] else f'{files.get(target, target)}:{qual}'

    def line(key, text, row, function=''):
        place = f'{row["file"]}:{row["line"]}'
        found.lines.append(Line('loosened', f'loosened:{key}', function, text, LOOSENED_STEP, (place,), (f'comment at {place}',)))

    def added(new, old):
        """The positions of `new` the baseline's `old` did not allow."""
        return sorted(new.keys() - old.keys())

    for name in sorted(then.keys() | now.keys()):
        old, new = then.get(name), now.get(name)
        if new is not None:
            for exception in added(new['alone'], old['alone'] if old else {}):
                row = new['alone'][exception]
                line(f'except:{name}:{exception}', f'except={spelled(exception, row)} added to together {name}', row)
        if old is not None and old['pairs']:
            if new is None or not new['pairs']:
                line(f'together:{name}', f'together {name} {",".join(old["pairs"])} removed', next(iter(old['pairs'].values())))
            else:
                for partner in sorted(old['pairs'].keys() - new['pairs'].keys()):
                    line(f'partner:{name}:{partner}', f'{partner} removed from together {name}', old['pairs'][partner])
                for on in sorted(set(new['on']) - set(old['on']) - {''}):
                    was = ', '.join(f'on={value}' for value in sorted(set(old['on']) - {''}))
                    line(f'on:{name}:{on}', (f'on={on} replaces {was} in together {name}' if was else f'on={on} added to together {name}'),
                         new['on'][on])
        if old is not None and old['writers']:
            if new is None or not new['writers']:
                line(f'writers:{name}', f'writers {name} removed', next(iter(old['writers'].values())))
            else:
                for writer in added(new['writers'], old['writers']):
                    row = new['writers'][writer]
                    line(f'writer:{name}:{writer}', f'{spelled(writer, row)} added to writers {name}', row)
    for (name, function), rows in sorted(same_then.items()):
        for row in rows[len(same_now.get((name, function), ())):]:
            line(f'same:{name}:{function}', f'same {name} removed from {row["file"]}:{row["qual"]}', row, function)
    return found


def field_impact(change, index):
    """One `impact` line (4.6) per function this change edits or adds whose set of written fields (`Model.field`
    or `table.column`, bookkeeping columns aside) differs from the baseline code's: the fields it now writes and no
    longer writes, how many other production functions write the first of them (seed, backfill and migration
    scripts aside) and whether several files write it without a writers agreement (an open `writers:` problem), and
    how many functions read its model (`MapHandle.queries`, and `MapHandle.sql_reads` of its table; model-level, tests
    included). Counts and one name only;
    `show NAME` lists them. A test's, a seed script's or a module's own code is no function this reports."""
    from .health import _test_files, written_field, writers
    from .signals import Line
    found = Findings()
    touched = change.touched() if change.baseline else set()
    if not touched:
        return found
    graph = change.graph
    tests = _test_files(graph)

    def fields(rows):
        by_function = {}
        for row in rows:
            if (key := written_field(row, tests)) is not None and not seeding(row['file']):
                by_function.setdefault(row_function(row), {}).setdefault(key, row)
        return by_function

    now, then = fields(change.writes()), None
    open_writers, readers_of = None, {}
    for function in sorted(touched):
        written = now.get(function, {})
        if then is None:
            then = fields(change.baseline_writes())
        before = then.get(function, {})
        added, removed = sorted(written.keys() - before.keys()), sorted(before.keys() - written.keys())
        if not added and not removed:
            continue
        shown = (added or removed)[0]
        row = written[shown] if shown in written else before[shown]      # a field it no longer writes: the baseline's row
        model = shown.rpartition('.')[0]
        others = sorted({other for other, items in now.items() if other != function and shown in items})
        table = row.get('table') or model         # SQL that reads the table (FROM, JOIN) reads the model too
        if (model, table) not in readers_of:
            readers_of[model, table] = sorted({row_function(query) for query in [*graph.queries(model), *graph.sql_reads(table)]})
        readers = readers_of[model, table]
        if open_writers is None:
            open_writers = {issue.name for issue in writers(change, index).issues}
        qual = function.partition(':')[2] or function
        text = (f'{qual} now writes {", ".join(added)}' if added else f'{qual} no longer writes {", ".join(removed)}') \
            + (f'; no longer writes {", ".join(removed)}' if added and removed else '') \
            + f'; {_counted(len(others), "other writer")}' + (' (no writers agreement)' if f'writers:{shown}' in open_writers else '') \
            + f', {_counted(len(readers), "reader")} of {model}'
        here = f'{row["file"]}:{qual}'
        detail = tuple(f'other writer of {shown}: {other}' for other in others[:10]) \
            + tuple(f'reader of {model}: {reader}' for reader in readers[:10])
        found.lines.append(Line('impact', f'impact:{function}', function, text,
                                f'check them for this change only (python -m flowguard show {shown})', (here,), detail))
    return found


def static_findings(cfg, graph, index, base=None, *, everything=False, replay=False):
    """The one assembly of owner and structure findings. Without replay (pytest, `check --static`): owner
    writes and pairs, values outside declared sets, declarations of one name that differ, deletes that leave
    children, missing columns and the open structure problems (`health`). `replay` (`check`) also runs copy
    discovery and the changed-alone comparison. `everything` (`--all`) compares every look-alike, not only those this
    change touches. The catalog's findings (`sources.findings`), what the change loosened, the fields it newly
    writes and the documents that describe code it edits (`docs.findings`) join the same list."""
    from . import health, sources
    change = Change(cfg, graph, baseline(cfg, base))
    copies = health.copies(change, index)
    found = owner_writes(change, index).extend(owner_pairs(change, index))
    found.extend(sources.findings(cfg, graph, change))
    found.extend(loosened(change, index))
    found.extend(field_impact(change, index))
    from . import docs                  # a document's text that describes code this change edits
    found.extend(docs.findings(change, touched_functions(change), everything=everything))
    found.extend(health.values(change))
    if change.baseline or everything:
        found.extend(declarations_differ(change))
    found.extend(health.deletes(change)).extend(health.columns(change))
    found.extend(health.delete_rules(change))
    found.extend(copies).extend(health.writers(change, index)).extend(health.uncreated(change))
    found.extend(health.labels(change))
    if replay:
        found.extend(discover(cfg, graph, index, change, everything=everything))
        found.extend(changed_alone(cfg, graph, index, change))
    found = families_ran(health.assess(found), index)
    found.ran.add('pair')
    found.touched_functions, found.touched_files = touched_functions(change), frozenset(change.files)
    return found


def touched_functions(change):
    """The functions a finding's member is touched by (`signals.deliver`): those this change edits or adds
    (`Change.touched`), and the module of each SQL file it changes, whose statements are that module's own code."""
    if not change.baseline:
        return frozenset()
    return frozenset(change.touched() | {change._modules[file] for file in change.files
                                         if file.endswith('.sql') and file in change._modules})


# ---- replay of candidate functions (check only) ------------------------------------------------------

class _Timeout(BaseException):
    """Raised into a replay that ran too long; not an Exception, so replay never records it as a result."""


@contextmanager
def watchdog(seconds):
    """Interrupt this thread after `seconds` (Windows too: the interpreter's async exception, no signal).
    The interruption is never withdrawn with a NULL exception: on Python 3.11 that leaves the eval breaker
    set, and a traced frame then loops at its first instruction for ever. One sent but not yet raised when
    the block ends is let through here and dropped."""
    target, lock, done = threading.get_ident(), threading.Lock(), threading.Event()
    state = dict(finished=False, fired=False)
    def watch():
        if done.wait(seconds):
            return
        with lock:
            if not state['finished']:
                state['fired'] = True
                ctypes.pythonapi.PyThreadState_SetAsyncExc(ctypes.c_ulong(target), ctypes.py_object(_Timeout))
    thread = threading.Thread(target=watch, name='flowguard-copy-watchdog', daemon=True)
    thread.start()
    arrived = False
    try:
        yield
    except _Timeout:
        arrived = True
        raise
    finally:
        with lock:
            state['finished'] = True
        done.set()
        if state['fired'] and not arrived:
            try:
                for _ in range(1_000_000):
                    pass        # the interpreter raises a pending interruption at this loop's jump back
            except _Timeout:
                pass  # Sent after the block ended (or caught inside it): the block is over, nothing to interrupt.


def _replay(function, rows, names, previous=None):
    """Collect only the unified sealed executor's per-input outcomes, without importing the project."""
    from .runtime import sealed
    def run(source):
        return [sealed(source, function['qual'], [row[name] for name in names], {}) for row in rows]
    outcomes = run(function['source'])
    if all(value['status'] == 'unavailable' for value in outcomes):
        return None, '; '.join(dict.fromkeys(value['reason'] for value in outcomes))
    before = run(previous) if previous is not None else outcomes
    return dict(now=outcomes, before=before,
                compared=previous is not None and any(_same(a, b) is not None for a, b in zip(before, outcomes))), ''


def _same(left, right):
    """Equal sealed outcomes; unavailable inputs and the same raised exception are not comparisons."""
    from .runtime import outcome_equal
    if left['status'] == 'unavailable' or right['status'] == 'unavailable':
        return None
    if left['status'] == right['status'] == 'raised':
        return None if left['error'] == right['error'] else False
    return left['status'] == right['status'] == 'ok' and outcome_equal(left['value'], right['value'])


def _show(value):
    from .cells import show
    return show(value)


def _outcome(value):
    return f'raised {value["error"]["type"]}' if value['status'] == 'raised' else _show(value['value'])


def _not_compared(left, right):
    missing = [(a, b) for a, b in zip(left, right) if _same(a, b) is None]
    reasons = [value['reason'] for pair in missing for value in pair if value['status'] == 'unavailable']
    if any(a['status'] == b['status'] == 'raised' for a, b in missing):
        reasons.append('same raised exception')
    return f'{len(missing)}/{len(left)} inputs not compared: ' + '; '.join(dict.fromkeys(reasons)) if missing else ''


def _order(rows, names):
    """Row indexes in the fixed comparison order: non-finite values, then the representatives (halves and
    small whole numbers from negative up), then boundaries and the code's own literals."""
    import math
    from .cells import representatives
    def rank(index):
        row = rows[index]
        special = [['nan', 'inf', '-inf'].index(repr(row[name])) for name in names
                   if type(row[name]) is float and not math.isfinite(row[name])]
        if special:
            return 0, min(special), index
        fixed = [repr(value) for name in names for value in representatives(_kind_of(row[name]))]
        return 1, min((fixed.index(repr(row[name])) for name in names if repr(row[name]) in fixed), default=len(fixed)), index
    return sorted(range(len(rows)), key=rank)


def _example(rows, names, mine, reference, label='reference'):
    """The first differing finite value and the first differing non-finite one, in the fixed
    representative order (halves, negatives, zero, then boundaries), and how many more differ."""
    import math
    differing = [(rows[index], mine[index], reference[index]) for index in _order(rows, names)
                 if _same(mine[index], reference[index]) is False]
    finite = [item for item in differing if all(not (type(item[0][n]) is float and not math.isfinite(item[0][n])) for n in names)]
    chosen = finite[:1] + [item for item in differing if item not in finite][:1]
    text = '; '.join(', '.join(f'{name}={_show(row[name])}' for name in names) + f' -> {_outcome(a)}({label} returns {_outcome(b)})'
                    for row, a, b in chosen)
    return text + (f'; plus {len(differing) - len(chosen)} other differences' if len(differing) > len(chosen) else '')


def _kind_of(value):
    from .cells import Kind
    return Kind({float: 'float', int: 'int'}.get(type(value), 'dec' if type(value).__name__ == 'Decimal' else 'other'))


# ---- copy discovery against a registered reference ----------------------------------------------------

def _functions(graph, cfg):
    """Callable module-level production functions, with their body shape, numeric constants and sizes."""
    from pathlib import Path
    from flowguard.structure.store import shape_list
    from .runtime import _functions as definitions
    rows, trees, sources = [], {}, {}
    tool = Path(__file__).resolve().parents[1]          # the running FlowGuard package never replays itself
    for ident, file, module, qual, line, end, blob in graph.con.execute(
            "SELECT n.id, n.file, n.module, n.qual, n.line, n.end_line, n.shape FROM node n JOIN file f ON f.path = n.file "
            "WHERE n.kind = 'function' AND f.is_test = 0 AND n.file LIKE '%.py' ORDER BY n.id"):
        path = (cfg.root / file).resolve()
        if '.' in qual or path.is_relative_to(cfg.intent) or path.is_relative_to(tool):
            continue                    # a nested function has no importable name of its own
        if file not in trees:
            try:
                sources[file] = read_source(cfg.root / file)
                trees[file] = dict(definitions(ast.parse(sources[file])))
            except (SyntaxError, OSError, UnicodeError):
                trees[file] = {}
        node = trees[file].get(qual)
        if node is None:
            continue
        if (file, '') not in trees:
            trees[(file, '')] = _module_literals(ast.parse(sources[file]))
        rows.append(dict(id=ident, file=file, module=module, qual=qual, line=line, end=end or line,
                         shape=set(shape_list(blob) if isinstance(blob, bytes) else blob or ()), node=node,
                         constants=_numbers(node), simple=_simple_parameters(node), source=sources[file],
                         literals=_own_literals(node, trees[(file, '')])))
    return rows


_UNREADABLE = object()


def _module_literals(tree):
    """A module's top-level `NAME = literal` constants, {name: (value, line)}, read from source and never run: the
    tables `_own_literals` takes the members of."""
    from .cache import _literal
    found = {}
    for statement in tree.body:
        targets = statement.targets if isinstance(statement, ast.Assign) else [statement.target] \
            if isinstance(statement, ast.AnnAssign) and statement.value is not None else []
        for target in targets:
            value = _literal(statement.value, _UNREADABLE)
            if isinstance(target, ast.Name) and value is not _UNREADABLE:
                found[target.id] = (value, statement.lineno)
    return found


def _own_literals(node, constants):
    """The strings and numbers a function's own code spells: its constants (no docstring) and the
    members of the module constants it reads (an alias table's keys and values)."""
    body = node.body[1:] if ast.get_docstring(node) is not None else node.body
    found = [n.value for statement in body for n in ast.walk(statement) if isinstance(n, ast.Constant)]
    for name in sorted({n.id for statement in body for n in ast.walk(statement)
                        if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load) and n.id in constants}):
        value = constants[name][0]
        found.extend([*value.keys(), *value.values()] if isinstance(value, dict) else
                     list(value) if isinstance(value, (tuple, list, set, frozenset)) else [value])
    return list(dict.fromkeys(value for value in found if type(value) in (str, int, float)))


def _numbers(node):
    return {n.value for n in ast.walk(node) if isinstance(n, ast.Constant) and type(n.value) in (int, float)
            and n.value not in TRIVIAL}


def _simple_parameters(node):
    """The positional parameter names when all are simple or unannotated; None for any other signature."""
    from .anchors import _annotation, _parameter_role
    arguments = node.args
    if arguments.vararg or arguments.kwarg or arguments.kwonlyargs:
        return None
    names = [a for a in (*arguments.posonlyargs, *arguments.args)]
    if any(_parameter_role(_annotation(a.annotation)) != 'input' and _annotation(a.annotation) not in LOOSE for a in names):
        return None
    return [a.arg for a in names]


LOOSE = {'object', 'Any', 'typing.Any'}      # annotations that say nothing about the input: read as unannotated


def _inferred(values):
    """The input kind a function's own literals suggest for an unannotated (or Any/object) parameter."""
    from .cells import Kind
    kinds = {type(value) for value in values}
    return Kind('str') if str in kinds else Kind('float') if kinds & {int, float} else None


def _similarity(a, b):
    return len(a & b) / len(a | b) if a and b else 0.0


def _look_alikes(functions, home, excluded):
    """Copy candidates of one function: the same number of simple parameters, and a similar body shape
    or a shared number other than 0, 1, -1 and 2. Static; size never excludes a function."""
    return [row for row in functions if row['id'] != home['id'] and row['id'] not in excluded and row['simple'] is not None
            and home['simple'] is not None and len(row['simple']) == len(home['simple'])
            and (_similarity(row['shape'], home['shape']) >= SIMILAR_SHAPE or row['constants'] & home['constants'])]


def look_alikes(cfg, graph, target, excluded=()):
    """`show`'s static copy pointers for a function: look-alikes that were not run, with the reason."""
    functions = _functions(graph, cfg)
    home = next((row for row in functions if row['id'] == target), None)
    if home is None:
        return []
    out = []
    for row in _look_alikes(functions, home, set(excluded)):
        shape, shared = _similarity(row['shape'], home['shape']), sorted(row['constants'] & home['constants'])
        reasons = ([f'similar body {shape:.2f}'] if shape >= SIMILAR_SHAPE else []) + \
                  ([f'shared number {", ".join(map(repr, shared))}'] if shared else [])
        # Its own strength: `strong` means the same decision sites (structure/homes.py); a look-alike was
        # neither run nor matched by site, so a different field or boundary may share its shape.
        out.append(dict(id=row['id'], file=row['file'], line=row['line'], how='look-alike', strength='look-alike',
                        score=round(shape, 2), reason='look-alike, not run: ' + '; '.join(reasons)))
    return sorted(out, key=lambda row: (-row['score'], row['id']))


def _classes(cfg, anchor, literals=()):
    """The owner's case classes, fixed numeric representatives and the literals of the compared code,
    one row set for every candidate; (rows, kinds, reason)."""
    from . import anchors, cells as C, differences as D
    if any(p.role == 'context' and p.source_type not in LOOSE for p in anchor.parameters):
        return None, {}, 'reference needs test-context arguments; no cases can run independently'
    try:
        view = anchors.decision_reading(cfg.root, anchor)
    except (ValueError, SyntaxError, OSError) as error:
        return None, {}, f'reference is unavailable: {error}'
    kinds = dict(view.kinds)
    for parameter in anchor.parameters:
        if parameter.name not in kinds and (kind := _inferred(literals)) is not None:
            kinds[parameter.name] = kind
    if not kinds or set(kinds) != {p.name for p in anchor.parameters}:
        return None, {}, 'reference inputs are not simple types'
    if set(view.kinds) == set(kinds):
        rows = [dict(region.inputs) for region in D.joint_partition(view, view).regions]
    else:
        rows = [{name: (C.points(kind, [v for v in literals if kind.accepts(v)]) or [C.OTHER])[0] for name, kind in kinds.items()}]
    points = {name: [row[name] for row in rows] for name in kinds}
    extra = {name: [C.coerce(value, kind) for value in literals if kind.accepts(C.coerce(value, kind))] for name, kind in kinds.items()}
    return D._with_representatives(rows, kinds, points, [], extra), kinds, ''


def _category(same, total, shape):
    """A look-alike that answers as the reference on `same` of `total` representative values: a copy (all of them), a
    diverged copy (at least half, with a similar body `shape`), or None."""
    if same == total:
        return 'copy'
    if 2 * same >= total and shape >= SIMILAR_SHAPE:
        return 'diverged copy'
    return None


def discover(cfg, graph, index, change, *, everything=False):
    """Unregistered look-alikes of each reference (`same NAME ref`), grouped by their results on its classes: a `copies:` finding
    of each diverged copy and each copy this change adds beside a reference the baseline had. A reference whose
    classes cannot be built or that cannot run itself, and a look-alike that cannot run or has no comparable input,
    leave copy discovery incomplete (`COPY_DISCOVERY` is not in `found.ran`)."""
    found = Findings()
    owners = _references(index)
    if not owners:
        return found
    started = time.perf_counter()
    functions = _functions(graph, cfg)
    by_id = {row['id']: row for row in functions}
    registered = {a.target for a in index.entries if a.kind == 'sensor'}
    impact = change.impact() if change.baseline else dict(added=[], changed=[])
    added, edited = set(impact['added']), set(impact['changed'])
    candidates_seen, complete = 0, True      # complete: every candidate of every reference compared
    for owner in owners:
        home = by_id.get(owner.target)
        if home is None:
            complete = False
            continue
        old_owner = _owner_at_baseline(change, owner)
        names = [p.name for p in owner.parameters]
        candidates = [row for row in _look_alikes(functions, home, registered) if len(row['simple']) == len(names)]
        new_owner = change.baseline and not old_owner
        shown = [row for row in candidates if everything or new_owner or row['id'] in added
                 or row['file'] in change.files]
        candidates_seen += len(candidates)
        complete = complete and len(shown) == len(candidates)       # all of them only with --all or a new reference
        if not shown:
            continue
        # One row set for all: the owner's classes, fixed representatives and every compared function's literals.
        rows, kinds, reason = _classes(cfg, owner, list(dict.fromkeys(
            value for row in (home, *shown) for value in row['literals'])))
        label = f'{owner.name} ({owner.file}:{owner.target_line})'
        reference = None if reason else _replay(home, rows, names)[0]
        if reference is None:
            complete = False
            continue
        groups, unclear = {}, False
        for row in shown:
            result, _ = _replay(row, rows, names)
            outcomes = result['now'] if result is not None else ()
            compared = [_same(a, b) for a, b in zip(outcomes, reference['now']) if _same(a, b) is not None]
            if not compared:
                unclear = True          # it cannot run, or has no comparable input
                continue
            category = _category(sum(compared), len(compared), _similarity(row['shape'], home['shape']))
            if category is None:
                continue
            # Grouped by the first difference from the owner in the fixed representative order.
            first = next(((index, _outcome(a)) for index in _order(rows, names)
                          for a, b in [(outcomes[index], reference['now'][index])] if _same(a, b) is False), None)
            groups.setdefault((category, first), []).append((row, outcomes))
        complete = complete and not unclear
        order = {'copy': 0, 'diverged copy': 1}
        for (category, _), group in sorted(groups.items(), key=lambda item: (order[item[0][0]], item[1][0][0]['id'])):
            members = [row for row, _ in group]
            places = '  '.join(f'{row["file"]}:{row["line"]}' for row in members)
            if category == 'copy':
                compared_count = sum(_same(a, b) is not None for a, b in zip(group[0][1], reference['now']))
                text = f'{category}: {len(members)} copies (match the reference on {compared_count} representative values; not a proof): {places}'
            else:
                apart = len({tuple(str(value) for value in outcomes) for _, outcomes in group}) > 1
                text = (f'{category} {len(members)} copies: {_example(rows, names, group[0][1], reference["now"])}: {places}'
                        + ('(same first difference; these copies also differ on other representative values)' if apart else ''))
            fresh = [row for row in members if row['id'] in added]
            # The 4.3 finding: a copy of the reference is a `copies:` member (a structure finding, never red, D1); one this
            # change adds or edits is new (its baseline version is not compared here, so it never was broken at the task
            # start), the reference and the copies the baseline had as they were are old (the agreement is the current one).
            from .health import Issue, LINES_ONLY
            parts = tuple((row['id'], f'{row["file"]}:{row["qual"]}', f'is a {category} of the reference {owner.file}:{owner.qual}',
                           f'call {owner.qual}') for row in members)
            facts = dict(family='copies', subject=f'copies of {owner.name}', parts=parts,
                         fresh=frozenset(row['id'] for row in members if row['id'] in added and old_owner or row['id'] in edited))
            if category == 'diverged copy':
                found.issues.append(Issue(f'copies:{owner.name}', 5, f'copy {owner.name}', f'reference {label}: {text}',
                                          f'choose one for each copy: call {owner.qual}; or write # flowguard: same {owner.name} above the copy and make it agree; '
                                          f'or, for copies meant to differ, python -m flowguard known add copies:{owner.name} --act ignore --why TEXT records that',
                                          frozenset({owner.target, *(row['id'] for row in members)}),
                                          frozenset({owner.file, *(row['file'] for row in members)}), **facts))
            elif category == 'copy' and fresh and old_owner:
                found.issues.append(Issue(f'copies:{owner.name}', LINES_ONLY, f'copy {owner.name}', f'reference {label}: {text}',
                                          f'call {owner.qual}', frozenset(row['id'] for row in members),
                                          frozenset(row['file'] for row in members), **facts))
    found.stats.update(copy_candidates=candidates_seen, copy_seconds=time.perf_counter() - started)
    if complete:
        found.ran.add(COPY_DISCOVERY)
    return found


def _references(index):
    """The registered references (`same NAME ref` on a production function) whose unregistered copies `discover`
    looks for."""
    return [a for a in index.entries if a.kind == 'sensor' and a.owner and a.source_role == 'production' and not a.issues]


STRUCTURAL_COPIES, COPY_DISCOVERY = 'structural copies', 'copy discovery'     # the two checks naming `copies:` findings


def families_ran(found, index):
    """Put into `found.ran` the families every check of which judged the whole project in this run, as a known
    entry's `known fixed?` needs (`signals.deliver`): the checks add their family themselves, except `copies`, whose
    findings come from two checks: the structural one (`health.copies`, every run) and copy discovery (`discover`,
    `check` only, the copies of each registered reference; all of them only with `--all`). The family ran when the
    first did and the second did too, or there is no reference whose copy it could name. The changed-alone
    comparison judges only what a change edits, so its family never ran in this sense."""
    if STRUCTURAL_COPIES in found.ran and (COPY_DISCOVERY in found.ran or not _references(index)):
        found.ran.add('copies')
    else:
        found.ran.discard('copies')
    return found


def _owner_at_baseline(change, owner):
    """Did the baseline commit already declare this owner (same name and function)?"""
    if not change.baseline:
        return False
    text = change.old_text(owner.file)
    if text is None or 'flowguard:' not in text:
        return False
    from .anchors import foreign_owners, source_facts
    if not owner.file.endswith('.py'):
        rows = foreign_owners(text, owner.module, owner.file).get('anchors', ())
    else:
        try:
            tree = ast.parse(text)
        except SyntaxError:
            return False
        rows = source_facts(tree, text, owner.module, owner.file).get('anchors', ())
    if owner.kind == 'owner':                   # a data owner: the same rule, its pairs included
        return any(row['kind'] == 'owner' and row['name'] == owner.name and tuple(row.get('pairs', ())) == owner.pairs
                   for row in rows)
    return any(row['name'] == owner.name and row['qual'] == owner.qual and row.get('owner') for row in rows)


# ---- one changed, its former twins not (unregistered too) ---------------------------------------------

def changed_alone(cfg, graph, index, change):
    """A changed function whose old version agreed with unchanged look-alikes on every representative
    value, while the new one differs: those copies probably needed the same change. When one of the changed
    functions has a flowguard comment (`same NAME`), that name's `changed-alone:` finding (red) names them."""
    from . import cells as C
    from .anchors import Parameter, parameter_kind, _annotation
    found = Findings()
    if not change.baseline:
        return found
    started = time.perf_counter()
    impact = change.impact()
    touched = set(impact['changed']) | set(impact['added'])
    if not any(ident.partition(':')[0] for ident in impact['changed']):
        return found                      # nothing changed: no function to compare with its look-alikes
    functions = _functions(graph, cfg)
    by_id = {row['id']: row for row in functions}
    anchored = {a.target: a for a in index.entries if a.kind == 'sensor'}
    alone, examined = {}, 0
    for ident in sorted(set(impact['changed'])):
        row = by_id.get(ident)
        old_text = change.old_text(row['file']) if row else None
        if row is None or row['simple'] is None or not row['simple'] or old_text is None:
            continue
        from .runtime import _functions as definitions
        try:
            old_node = dict(definitions(ast.parse(old_text))).get(row['qual'])
        except SyntaxError:
            continue
        if old_node is None or _simple_parameters(old_node) != row['simple']:
            continue
        from flowguard.structure.extract import own_nodes, shape, strip_doc
        old_shape = set(shape(own_nodes(strip_doc(old_node.body))))
        old_numbers = _numbers(old_node)
        peers = [other for other in functions if other['id'] not in touched
                 and other['simple'] is not None and len(other['simple']) == len(row['simple'])
                 and (_similarity(other['shape'], old_shape) >= SIMILAR_SHAPE or other['constants'] & old_numbers)]
        peers = sorted(peers, key=lambda other: (-_similarity(other['shape'], old_shape), other['id']))[:PEERS]
        if not peers:
            continue
        kinds = {}
        for argument in (*row['node'].args.posonlyargs, *row['node'].args.args):
            try:
                kind = parameter_kind(Parameter(argument.arg, '', _annotation(argument.annotation), 'input', True), 0.0)
            except ValueError:
                kind = None
            if kind is None:
                break
            kinds[argument.arg] = kind
        if len(kinds) != len(row['simple']):
            continue
        literals = [n.value for tree in (old_node, row['node']) for n in ast.walk(tree) if isinstance(n, ast.Constant)]
        axes = {name: list(dict.fromkeys([*C.points(kind, [C.coerce(v, kind) for v in literals if kind.accepts(C.coerce(v, kind))]),
                                          *C.representatives(kind)], ))
                for name, kind in kinds.items()}
        base = {name: values[0] for name, values in axes.items()}
        rows = [dict(base, **{name: value}) for name, values in axes.items() for value in values]
        mine, why = _replay(row, rows, row['simple'], old_text)
        missing = _not_compared(mine['before'], mine['now']) if mine is not None else why
        if missing:
            found.lines.append(_not_compared_line(row, missing))
        if mine is None or not mine['compared'] or not any(_same(a, b) is False for a, b in zip(mine['before'], mine['now'])):
            continue            # no comparable old version, or the edit kept every representative's result
        examined += 1
        twins = []
        for peer in peers:
            theirs, _ = _replay(peer, rows, row['simple'])
            if theirs is None:
                continue
            if missing := _not_compared(mine['before'], theirs['now']):
                found.lines.append(_not_compared_line(peer, missing))
            comparison = [_same(a, b) for a, b in zip(mine['before'], theirs['now']) if _same(a, b) is not None]
            if comparison and all(comparison) and any(_same(a, b) is False for a, b in zip(mine['now'], theirs['now'])):
                twins.append(peer)
        if twins:
            alone[row['id']] = (row, sorted(twins, key=lambda peer: peer['id']))
    merged = {}
    for row, twins in alone.values():     # several edits that left the same copies behind: one finding
        merged.setdefault(tuple(peer['id'] for peer in twins), (twins, []))[1].append(row)
    for twins, changed in merged.values():
        # The owner among the changed is the one named: its copies follow it, as the same-name red says.
        owned = [item for item in changed if item['id'] in anchored and anchored[item['id']].owner]
        row = owned[0] if owned else min(changed, key=lambda item: (len(item['qual']), item['qual']))
        anchor = anchored[row['id']] if owned else next((anchored[item['id']] for item in changed if item['id'] in anchored), None)
        if anchor is None:
            continue            # only a changed function with a flowguard comment has a finding
        # The owner is the reference: its copies follow it, and a copy that left it goes back to it. Without
        # one among them no copy is chosen: an intended change goes to every copy, any other is undone.
        owner = next((peer for peer in twins if peer['id'] in anchored and anchored[peer['id']].owner
                      and anchored[peer['id']].name == anchor.name), None)
        quals = ', '.join(item['qual'] for item in changed)
        if anchor.owner:
            step = f'update together, or call {row["qual"]}'
        elif owner:
            step = f'make {quals} match reference {owner["qual"]}({owner["file"]}:{owner["line"]})'
        else:
            step = f'first decide which copy is correct: for an intended change, update together or call {row["qual"]}; otherwise make {quals} return to the original behavior'
        found.issues.append(_changed_alone_issue(anchor, changed, twins, _ascii(step)))
    found.stats.update(changed_examined=examined, changed_seconds=time.perf_counter() - started)
    return found


def _not_compared_line(row, reason):
    """A `not compared` line of the changed-alone comparison: a function whose old and new results (or a copy's)
    could not be compared on some inputs."""
    from .signals import Line
    place = f'{row["file"]}:{row["qual"]}'
    return Line('not compared', 'not compared:' + row['id'], row['id'], f'{place} ({reason})', 'not a failure', (place,), (reason,))


def _changed_alone_issue(anchor, changed, twins, step):
    """The `changed-alone:` finding of one registered name: one member per changed function whose unchanged former
    copies now answer differently. New by construction: the comparison is this change's old against its new code."""
    from .health import Issue, LINES_ONLY
    copies = '  '.join(f'{peer["file"]}:{peer["qual"]}' for peer in twins)
    what = (f'changed behavior; {_counted(len(twins), "copy", "copies")} that answered the same '
            + ('is' if len(twins) == 1 else 'are') + f' unchanged: {copies}')
    parts = tuple((item['id'], f'{item["file"]}:{item["qual"]}', what, step) for item in changed)
    return Issue(f'changed-alone:{anchor.name}', LINES_ONLY, f'changed alone {anchor.name}',
                 f'{anchor.name}: ' + ', '.join(place for _, place, _, _ in parts) + ' ' + what, step,
                 frozenset(item['id'] for item in changed), frozenset(item['file'] for item in changed),
                 family='changed-alone', subject=f'same {anchor.name}', parts=parts,
                 fresh=frozenset(item['id'] for item in changed))


def check_findings(cfg, graph, index, base=None, *, everything=False, static=None):
    """`check`: the static findings with copy discovery and the changed-alone comparison."""
    if static is None:
        return static_findings(cfg, graph, index, base, everything=everything, replay=True)
    # Pytest already assembled the static facts. Replay remains outside its session and can add
    # copy issues; the combined summary counts those without running the static checks twice.
    from . import health
    change = Change(cfg, graph, baseline(cfg, base))
    found = discover(cfg, graph, index, change, everything=everything).extend(changed_alone(cfg, graph, index, change))
    return health.assess(families_ran(Findings().extend(static).extend(found), index))


def show_lines(cfg, graph, index, name):
    """`show NAME` of an owner, each agreement in its 4.3 spelling with its place: a writers agreement with the writes
    outside it, a together agreement with its except= functions, a reference (`same NAME ref`) with its unregistered
    look-alikes; and for a writers or together agreement the fix the red line leaves out (4.7: a red line names no
    way to silence it)."""
    lines = []
    for owner in index.named(name):
        if owner.kind == 'owner' and owner.writers:
            rows, fixtures, outside = _writers_rows(graph, owner)
            where = _agreement_place(graph, owner, "writers")
            lines.append(f'writers {owner.name} {",".join(_spelled(graph, owner.module, writer) for writer in owner.writers)} {where}')
            def plain(row):
                value = f', value {row["value"]!r}' if 'value' in row else ''
                return f'{row["file"]}:{row["line"]} {row["function"]} ({row["kind"]}{value})'
            lines.extend('outside writers: ' + plain(row) for row in outside)
            lines.extend('test fixture (not held): ' + plain(row) for row in fixtures if not _allowed(row, owner.writers))
            lines.extend('unclear: ' + plain(row) + f' {row.get("reason", "")}' for row in rows if row.get('unclear'))
            if outside:
                lines.append(f'fix: call {" or ".join(dict.fromkeys(map(_writer_name, owner.writers)))} instead; adding a '
                             f"function to the writers agreement ({where}) loosens it, which is the owner's decision")
        if owner.kind == 'owner' and owner.pairs:
            exceptions = ','.join(_spelled(graph, owner.module, item.partition('(')[0], path=True) + '(' + item.partition('(')[2]
                                  for item in owner.alone)
            lines.append(f'together {owner.name} {",".join(owner.pairs)}' + (f' on={owner.on}' if owner.on else '')
                         + (f' except={exceptions}' if exceptions else '') + f' {_agreement_place(graph, owner, "pairs")}')
            lines.append(_pair_fix(graph, owner))
        if owner.owner:
            functions = _functions(graph, cfg)
            home = next((row for row in functions if row['id'] == owner.target), None)
            registered = {a.target for a in index.entries if a.kind == 'sensor'}
            if home is None:
                continue
            similar = _look_alikes(functions, home, registered)
            lines.append(f'same {owner.name} ref {owner.file}:{owner.target_line}; {len(similar)} unregistered look-alikes '
                         '(not run here; check --all compares them)')
            lines.extend(f'look-alike {row["file"]}:{row["line"]} {row["qual"]}' for row in similar)
    return lines


def _writers_rows(graph, owner):
    """(every write of a writers agreement's field, also by field name alone; the test fixtures among them; the writes
    outside its writers that are neither unclear nor a fixture), as `show_lines` lists them."""
    tests = {path for (path,) in graph.con.execute('SELECT path FROM file WHERE is_test = 1')}
    rows = list(graph.writes(owner.name, by_name=True))
    fixtures = [row for row in rows if _test_write(graph, row, tests)]
    outside = [row for row in rows if not row.get('unclear') and not _allowed(row, owner.writers) and row not in fixtures]
    return rows, fixtures, outside


def agreement_writes(graph, index, name):
    """{(file, line, function, kind)} of the writes `show_lines` lists for the writers agreements of `name` (outside
    its writers, test fixtures it does not allow, unclear ones): `show` lists every other write of the field once."""
    listed = set()
    for owner in index.named(name):
        if owner.kind == 'owner' and owner.writers:
            rows, fixtures, outside = _writers_rows(graph, owner)
            listed.update((row['file'], row['line'], row['function'], row['kind']) for row in
                          [*outside, *(row for row in fixtures if not _allowed(row, owner.writers)),
                           *(row for row in rows if row.get('unclear'))])
    return listed


def _spelled(graph, module, position, *, path=False):
    """A writers or except= position (`module:function`) as a 4.3 comment in `module` spells it: a function of that
    file bare (except= needs its path, `path`), another file's path:function, a JS/TS function by its declared name
    (`anchors._declared_name`); a position the map does not hold as it is (its comment's line is red)."""
    from flowguard.structure import store
    from .anchors import _declared_name
    row = graph.con.execute('SELECT file, module, qual, raw FROM node WHERE id = ?', (position,)).fetchone()
    if row is None:
        return position
    file, own, qual, raw = row
    declared = _declared_name(file, qual, store.unpack(raw) if raw else {})
    return declared if own == module and not path else f'{file}:{declared}'


def _pair_fix(graph, owner):
    return (f'fix: also write {", ".join(owner.pairs)} in the same operation; an except=path:function(reason) on the '
            f'together agreement ({_agreement_place(graph, owner, "pairs")}) loosens it, which is the owner\'s decision and '
            'the next run shows as loosened')


def model_known(graph, model):
    """Does the map know `model`: a Prisma model of that name (or of that table, `@@map`), a SQL table, a top-level
    TS interface, class or type alias, or a class of the map (Python, C#)? `show Model.field` lists the zod keys of
    the field's name only for a model it knows (`declaration_lines`)."""
    folded = model.casefold()
    for schema in graph.schemas():
        if schema['kind'] == 'prisma':
            if any(item['name'] == model or (item.get('table') or '').casefold() == folded for item in schema.get('models', ())):
                return True
        elif any((item.get('name') or item.get('table') or '').casefold() == folded
                 for item in [*schema.get('tables', ()), *schema.get('changes', ())]):
            return True
    if model in graph.ts_type_files():
        return True
    return graph.con.execute("SELECT 1 FROM node WHERE kind = 'class' AND (qual = ? OR qual LIKE ?) LIMIT 1",
                             (model, '%.' + model)).fetchone() is not None


def field_absent(graph, model, field):
    """What the map knows `model` as when that has no field `field`: the Prisma models of that name or `@@map`
    table and the SQL tables of that name, whose fields and columns the map reads (`Prisma model Job (table
    jobs)`, `database table bookings`), and the top-level TS types of that name (`TS type Job`); [] when none of
    them is a Prisma model or SQL table, or one of them has the field: a Prisma field of that name or column
    (`@map`), a column of that name in a table of the model (its `@@map` table too) or one an `ALTER TABLE ... ADD`
    gives it, a TS type's member (a TS type that `extends` another, or whose members are not an
    object type, counts as having it). `show Model.field` then lists no zod key of that name, which would match by
    the name alone (`declaration_lines`)."""
    folded, column = model.casefold(), field.casefold()
    known, tables = [], {folded}
    for schema in graph.schemas():
        if schema['kind'] != 'prisma':
            continue
        for item in schema.get('models', ()):
            if item['name'] == model or (item.get('table') or '').casefold() == folded:
                if any(entry['name'] == field or (entry.get('column') or '').casefold() == column for entry in item.get('fields', ())):
                    return []
                tables.add((item.get('table') or item['name']).casefold())
                known.append(f'Prisma model {item["name"]}' + (f' (table {item["table"]})' if item['name'] != model else ''))
    for schema in graph.schemas():
        if schema['kind'] != 'sql':
            continue
        for table in schema.get('tables', ()):
            if table['name'].casefold() in tables:
                if table.get('columns') is None or any(entry['name'].casefold() == column for entry in table['columns']):
                    return []
                if table['name'].casefold() == folded:
                    known.append(f'database table {table["name"]}')
        for change in schema.get('changes', ()):
            if change['table'].casefold() in tables and (change['verb'] == 'copy' or any(
                    entry['name'].casefold() == column for entry in change.get('add', ()))):
                return []           # a CREATE TABLE ... AS SELECT does not spell its columns
    if not known:
        return []
    for path in sorted(graph.ts_type_files().get(model, ())):
        members = _ts_members(graph, path, model)
        if members is None or field in members:
            return []
        known.append(f'TS type {model}')
    return list(dict.fromkeys(known))


def _ts_members(graph, path, name):
    """The member names of the top-level TS interfaces, object type aliases and classes `name` of one file (its
    fields, methods and a constructor's parameter properties); None when one of them has members this does not
    read: it `extends` another, is a type alias of anything but an object type, or has an index signature."""
    from ..structure.readers.common import parse, text
    from ..structure.readers.registry import language_for
    source, tree = parse((graph.root / path).read_bytes(), language_for(path))
    members, seen = set(), False
    for statement in tree.root_node.named_children:
        node = statement.child_by_field_name('declaration') if statement.type == 'export_statement' else statement
        if node is None or node.type not in ('interface_declaration', 'type_alias_declaration', 'class_declaration',
                                             'abstract_class_declaration') \
                or text(node.child_by_field_name('name'), source) != name:
            continue
        seen = True
        body = node.child_by_field_name('value') if node.type == 'type_alias_declaration' else node.child_by_field_name('body')
        if body is None or body.type not in ('object_type', 'interface_body', 'class_body') or any(
                child.type == 'extends_type_clause' or child.type == 'class_heritage' and any(
                    part.type == 'extends_clause' for part in child.named_children) for child in node.named_children):
            return None
        for member in body.named_children:
            if member.type == 'index_signature':
                return None
            key = member.child_by_field_name('name')
            if key is not None:
                members.add(text(key, source)[1:-1] if key.type == 'string' else text(key, source))
            if member.type == 'method_definition' and text(key, source) == 'constructor':
                for parameter in member.child_by_field_name('parameters').named_children:
                    pattern = parameter.child_by_field_name('pattern')
                    if pattern is not None and pattern.type == 'identifier' and any(
                            child.type in ('accessibility_modifier', 'override_modifier') or child.type == 'readonly'
                            for child in parameter.children):
                        members.add(text(pattern, source))
    return members if seen else None


def _declared_by_tests(row):
    """Do only test files declare this value set (`MapHandle.value_sets` row): the files declaring a TS type's member
    with it (its `scope`), or the files of an enum or a CHECK (`is_test_file`, the map's test flag)?"""
    return all(map(is_test_file, row['scope'] if row['kind'] == 'ts-type' else row['files']))


def declaration_lines(graph, name):
    """`show NAME` (4.4): what the map already read about a name, ahead of who writes and reads it. For `Model.field`
    or `table.column`, each distinct declaration in the Prisma schemas and in the SQL files with the files that
    declare it so (declarations that differ between files are lines of their own), the value sets read for it (an
    enum of a schema in use, a CHECK, a TS type), the enum of each Prisma schema not in use that types the field
    (`unused_enum_lines`), and the zod number schemas of an object key of the field's name (`zod_bounds`; only for a
    model the map knows, `model_known`, and not for a field its Prisma models, SQL tables and TS types lack,
    `field_absent`); for a bare name, the value of a module-level literal constant (an array of
    literals too) and the members of a value set declared under that name. A value set or constant only test files
    declare is left out (`is_test_file`); a CHECK that code builds as a string and runs (`$executeRawUnsafe`) is not
    read: only `.sql` files give ranges and CHECK sets."""
    import json

    def where(places):
        return ', '.join(places[:3]) + (f' and {len(places) - 3} more' if len(places) > 3 else '')
    lines = []
    model, dot, field = name.partition('.')
    if dot and field and '.' not in field:
        if not model_known(graph, model):
            return lines
        declared, columns, tables = {}, {}, {model.casefold()}
        for schema in graph.schemas():
            for item in schema.get('models', ()) if schema['kind'] == 'prisma' else ():
                for column in item.get('fields', ()):
                    if item['name'] == model and column['name'] == field:
                        tables.add((item.get('table') or model).casefold())
                        text = column['type'] + ('[]' if column.get('list') else '') + ('?' if column.get('optional') else '')
                        text += f' {column["attributes"]}' if column.get('attributes') else ''
                        declared.setdefault(text, []).append(f'{schema["file"]}:{column["line"]}')
                        columns.setdefault('', set()).add((column.get('column') or field).casefold())
        wanted = columns.get('', set()) | {field.casefold()}
        sql, bounded = {}, {}
        for schema in graph.schemas():
            if schema['kind'] != 'sql':
                continue
            for table in schema.get('tables', ()):
                if table['name'].casefold() in tables:
                    for column in table.get('columns', ()):
                        if column['name'].casefold() in wanted:
                            sql.setdefault(f'{table["name"]}.{column["name"]} {column.get("type") or "(no type)"}', []).append(
                                f'{schema["file"]}:{column["line"]}')
            for item in [*schema.get('tables', ()), *schema.get('changes', ())]:
                if (item.get('name') or item.get('table') or '').casefold() in tables:
                    for bound in item.get('ranges', ()):
                        if bound['column'].casefold() in wanted:
                            low = f'{bound["low"]} {"<=" if bound["low_inclusive"] else "<"} ' if 'low' in bound else ''
                            high = f' {"<=" if bound["high_inclusive"] else "<"} {bound["high"]}' if 'high' in bound else ''
                            table_name = item.get('name') or item.get('table')
                            bounded.setdefault(f'{table_name}.{bound["column"]}: {low}{bound["column"]}{high}', []).append(
                                f'CHECK {schema["file"]}:{bound["line"]}')
        lines.extend(f'declared {name}: {text} ({where(places)})' for text, places in declared.items())
        lines.extend(f'column {text} ({where(places)})' for text, places in sql.items())
        lines.extend(f'range {text} ({where(places)})' for text, places in bounded.items())
        if not field_absent(graph, model, field):        # a key of a field the model lacks matches by its name alone
            lines.extend(f'zod key {field} in {schema}: {bounds} (' + where([f'{file}:{line}' for line in at]) + ')'
                         for (file, schema, bounds), at in zod_bounds(graph, field).items())
        sets = {}
        for item in graph.value_sets():
            if item['name'] == name and not _declared_by_tests(item):
                sets.setdefault(' | '.join(map(str, item['values'])), []).append(item['where'])
        lines.extend(f'values {name}: {values} ({where(places)})' for values, places in sets.items())
        lines.extend(unused_enum_lines(graph, model, field))
        return lines
    constants, sets, declared_at = {}, {}, set()
    for item in graph.declarations(exported=False):
        if item['name'] == name and not is_test_file(item['file']):
            sets.setdefault(' | '.join(map(str, item['values'])), []).append(f'{item["file"]}:{item["line"]}')
            declared_at.add((item['file'], item['line']))
    for row in graph.assignments():
        if row.get('target') == name and not row.get('field') and row.get('literal') and ':' not in row['node'] \
                and not is_test_file(row['file']) and (row['file'], row['line']) not in declared_at:
            constants.setdefault(json.dumps(row['value'], ensure_ascii=False), []).append(f'{row["file"]}:{row["line"]}')
    lines.extend(f'const {name} = {value} ({where(places)})' for value, places in constants.items())
    lines.extend(f'values {name}: {values} ({where(places)})' for values, places in sets.items())
    return lines


def unused_enum_lines(graph, model, field):
    """`values Model.field` lines of the Prisma enums that type the field in a schema the value gate does not read
    (`MapHandle.value_sets` holds the enums of the schemas in use): each schema not in use (`prisma_schemas_in_use`:
    a provider template such as `schema.sqlite.prisma`), and a guessed schema whose model a schema in use defines;
    the enum's members and where it is declared, one line per enum and set (`archived` files left out, as there)."""
    from flowguard.structure.readers.prisma import schema_folders
    in_use, guessed = graph.prisma_schemas_in_use(), graph.prisma_schemas_guessed()
    schemas = schema_folders(graph._live_prisma())
    defined = {item['name'] for schema in schemas if schema['files'][0] in in_use and schema['files'][0] not in guessed
               for item in schema['models']}
    found = {}
    for schema in schemas:
        first = schema['files'][0]
        if first in in_use and (first not in guessed or model not in defined):
            continue                    # value_sets holds this schema's enums
        why = 'a schema not in use' if first not in in_use else 'a guessed schema; a schema in use defines the model'
        enums = {enum['name']: enum for enum in schema['enums']}
        for item in schema['models']:
            if item['name'] != model:
                continue
            for column in item['fields']:
                enum = enums.get(column['type'])
                if column['name'] == field and enum and enum['fields']:
                    values = ' | '.join(member['name'] for member in enum['fields'])
                    found.setdefault((values, enum['name'], why), []).append(f'{enum["file"]}:{enum["line"]}')
    return [f'values {model}.{field}: {values} (enum {enum} {", ".join(places)}, {why if len(places) == 1 else why.replace("a schema", "schemas")})'
            for (values, enum, why), places in found.items()]


ZOD_BOUNDS = {'min': ('low', True), 'gte': ('low', True), 'gt': ('low', False), 'max': ('high', True),
              'lte': ('high', True), 'lt': ('high', False)}
ZOD_SIGNS = {'positive': ('low', '0', False), 'nonnegative': ('low', '0', True), 'negative': ('high', '0', False),
             'nonpositive': ('high', '0', True)}
ZOD_UNREAD = ('refine', 'superRefine', 'transform')     # checks a zod line names and does not read
ZOD_VALUES = {'parse', 'safeParse', 'parseAsync', 'safeParseAsync', 'spa', 'decode', 'decodeAsync', 'safeDecode',
              'safeDecodeAsync', 'encode', 'encodeAsync', 'safeEncode', 'safeEncodeAsync', 'isOptional', 'isNullable',
              'toJSONSchema'}       # the calls of a schema that return no schema: a parsed value, a flag
ZOD_OBJECTS = {'object', 'strictObject', 'looseObject', 'extend', 'safeExtend'}     # the calls a schema's shape is given to
CHAIN = {'call_expression', 'member_expression', 'parenthesized_expression', 'as_expression', 'satisfies_expression',
         'non_null_expression'}
SCOPES = {'program', 'statement_block', 'switch_case', 'switch_default'}       # where a `const` is visible


class _Source:
    """One JS/TS file's syntax for `zod_bounds`: its `const` declarations by the scope holding them, and the call
    chains and numbers they name."""

    def __init__(self, source, tree):
        from ..structure.readers.common import text, walk
        self.text = lambda node: text(node, source)
        self.constants = {}
        for declaration in walk(tree.root_node):
            if declaration.type != 'lexical_declaration' or declaration.children[0].type != 'const':
                continue
            scope = declaration.parent
            while scope is not None and scope.type not in SCOPES:
                scope = scope.parent
            for declarator in declaration.named_children:
                name, value = declarator.child_by_field_name('name'), declarator.child_by_field_name('value')
                if scope is not None and declarator.type == 'variable_declarator' and name is not None \
                        and name.type == 'identifier' and value is not None:
                    self.constants[scope.id, self.text(name)] = value

    def constant(self, node, name):
        """The value of the `const NAME` that `node` sees: the nearest enclosing scope's (a parameter of an
        enclosing function of that name hides the outer ones), else None."""
        from ..structure.readers.ecma import FUNCTIONS
        while node is not None:
            if node.type in SCOPES and (node.id, name) in self.constants:
                return self.constants[node.id, name]
            if node.type in FUNCTIONS and name in self.parameters(node):
                return None
            node = node.parent
        return None

    def parameters(self, function):
        """The names a function's parameters bind (their patterns; types and default values left out)."""
        names, stack = set(), [function.child_by_field_name(part) for part in ('parameters', 'parameter')]
        while stack:
            node = stack.pop()
            if node is None or node.type == 'type_annotation':
                continue
            if node.type in ('identifier', 'shorthand_property_identifier_pattern'):
                names.add(self.text(node))
                continue
            skip = [node.child_by_field_name('value') if node.type in ('required_parameter', 'optional_parameter') else None,
                    node.child_by_field_name('right') if node.type in ('assignment_pattern', 'object_assignment_pattern') else None,
                    node.child_by_field_name('key') if node.type == 'pair_pattern' else None]
            stack.extend(child for child in node.named_children if not any(child == other for other in skip if other is not None))
        return names

    def number(self, node):
        """A numeric constant's value as the source spells it (`2147483647`, `-2_147_483_648`), through
        parentheses, `as const` and `satisfies`; None for anything else."""
        from ..structure.readers.ecma import operator, unwrap
        node = unwrap(node)
        if node is not None and node.type == 'number':
            return self.text(node)
        if node is not None and node.type == 'unary_expression' and operator(node) in ('-', '+') and len(node.named_children) == 1:
            inner = self.number(node.named_children[0])
            return operator(node) + inner if inner is not None else None
        return None

    def number_steps(self, node, seen=frozenset()):
        """The calls of a zod number schema's chain after its base call (`z.number(`, `z.coerce.number(`), from
        the base outward, as [(method, call)]: those of each same-file or function-local `const` the chain starts
        from first (`fte.max(1)` of `const fte = z.number().min(0)`: min, then max); None when the chain is not a
        number schema (`z.string(`, `z.array(`, `.array()` of a number, `.parse(` of one, a name no such const
        holds)."""
        steps = []
        while node is not None and node.type in CHAIN:
            if node.type == 'call_expression':
                callee = node.child_by_field_name('function')
                if callee is None or callee.type != 'member_expression':
                    return None
                steps.append((self.text(callee.child_by_field_name('property')), node))
                node = callee.child_by_field_name('object')
            elif node.type == 'member_expression':
                steps.append((self.text(node.child_by_field_name('property')), None))
                node = node.child_by_field_name('object')
            else:
                node = node.named_children[0] if node.named_children else None
        if node is None or node.type != 'identifier':
            return None
        steps.reverse()
        if self.text(node) == 'z':
            names = [name for name, _ in steps[:2]]
            base = 1 if names[:1] == ['number'] and steps[0][1] is not None else \
                2 if names == ['coerce', 'number'] and steps[0][1] is None and steps[1][1] is not None else 0
            if not base:
                return None
            inner = []
        else:
            value = self.constant(node, self.text(node))
            if value is None or value.id in seen or (inner := self.number_steps(value, seen | {value.id})) is None:
                return None
            base = 0
        steps = inner + steps[base:]
        if any(call is None or name == 'array' or name in ZOD_VALUES for name, call in steps):
            return None                 # a property read, `.array()`, a parsed value: no number schema
        return steps

    def bound(self, call):
        """A bound call's first argument as the source spells it, a name with its value when a `const` it sees
        holds a number (`MAX_FTE_SHARE=2.0`); None without an argument."""
        from ..structure.readers.ecma import COMMENTS
        arguments = call.child_by_field_name('arguments')
        argument = next((child for child in arguments.named_children if child.type not in COMMENTS), None) \
            if arguments is not None else None
        if argument is None:
            return None
        if argument.type == 'identifier':
            value = self.constant(argument, self.text(argument))
            spelled = self.number(value) if value is not None else None
            return f'{self.text(argument)}={spelled}' if spelled is not None else self.text(argument)
        return ' '.join(self.text(argument).split())


def zod_bounds(graph, field):
    """{(file, schema object, bounds text): [line]} of the zod number schemas that an object key `field` is given in
    the TS/JS files outside tests, matched by the key's name alone. A key counts when its own schema chain is a
    number schema: its base call is `z.number(` or `z.coerce.number(`, directly (`field: z.number()...`) or through
    a `const NAME = ...` of the same file that the key names (`field: NAME...`; a function's own `const` for a key
    inside it), so an array, object or string key whose nested schemas hold numbers gets no line. The bounds are
    the constant's chain with the key's own chain after it, a later bound replacing an earlier one of the same side,
    as the source spells them: `min`, `gte`, `gt`, `max`, `lte`, `lt`, `positive()`, `nonnegative()`, `negative()`
    and `nonpositive()`; a bound that is a name stays that name, with its value as spelled when a `const` it sees
    holds a number (`MAX_FTE_SHARE=2`, `MIN_SAP_REFERENCE=-2_147_483_648`). A `refine`, `superRefine` or
    `transform` on the chain is named, not read (`, and a refine that is not read may reject more`). The schema
    object is the nearest enclosing `z.object(`/`.extend(` (also `strictObject`, `looseObject`, `safeExtend`)
    whose result the source names (`const NAME = z.object(`, `NAME: z.object(`), else the declaration holding the
    key (`const NAME = wrap(z.object(`), else `an unnamed object`. A text reading for `show`, which names each
    place."""
    from ..structure.readers.common import parse, text, walk
    from ..structure.readers.registry import ECMA, language_for
    found = {}
    pattern = re.compile(rb'\bz\s*\.')
    for (path,) in graph.con.execute('SELECT path FROM file ORDER BY path'):
        language = language_for(path)
        if language not in ECMA or is_test_file(path):
            continue
        data = (graph.root / path).read_bytes()
        if field.encode() not in data or not pattern.search(data):
            continue
        source, tree = parse(data, language)
        reader = _Source(source, tree)

        def head(call):
            """The node a call chain's value goes to: the end of `z.object({...}).strict().refine(...)`'s chain."""
            node = call
            while node.parent is not None and node.parent.type in CHAIN and (
                    node.parent.type != 'call_expression' or node.parent.child_by_field_name('function') == node):
                node = node.parent
            return node

        def named(node):
            """The name the source gives the value `node`: its declarator's or its key's, else None."""
            holder = node.parent
            if holder is not None and holder.type == 'variable_declarator' and holder.child_by_field_name('value') == node:
                return text(holder.child_by_field_name('name'), source)
            if holder is not None and holder.type == 'pair' and holder.child_by_field_name('value') == node:
                return key_text(holder.child_by_field_name('key'))
            return None

        def key_text(key):
            if key is None:
                return None
            if key.type in ('property_identifier', 'identifier'):
                return text(key, source)
            return text(key, source)[1:-1] if key.type == 'string' else None

        def schema_of(pair):
            holder = pair.parent
            while holder is not None:
                if holder.type == 'call_expression':
                    callee = holder.child_by_field_name('function')
                    method = callee.child_by_field_name('property') if callee is not None and callee.type == 'member_expression' else None
                    if method is not None and text(method, source) in ZOD_OBJECTS and (name := named(head(holder))):
                        return name
                holder = holder.parent
            holder = pair.parent
            while holder is not None and holder.type != 'variable_declarator':
                holder = holder.parent
            return text(holder.child_by_field_name('name'), source) if holder is not None else 'an unnamed object'

        for pair in walk(tree.root_node):
            if pair.type != 'pair' or key_text(pair.child_by_field_name('key')) != field:
                continue
            steps = reader.number_steps(pair.child_by_field_name('value'))
            if steps is None:
                continue
            bounds, unread = {}, []
            for method, call in steps:
                if method in ZOD_BOUNDS and (bound := reader.bound(call)) is not None:
                    side, inclusive = ZOD_BOUNDS[method]
                    bounds[side] = (bound, inclusive)
                elif method in ZOD_SIGNS:
                    side, bound, inclusive = ZOD_SIGNS[method]
                    bounds[side] = (bound, inclusive)
                elif method in ZOD_UNREAD and method not in unread:
                    unread.append(method)
            low = f'{bounds["low"][0]} {"<=" if bounds["low"][1] else "<"} ' if 'low' in bounds else ''
            high = f' {"<=" if bounds["high"][1] else "<"} {bounds["high"][0]}' if 'high' in bounds else ''
            shown = f'{low}{field}{high}' if bounds else f'{field} (no bounds)'
            if unread:
                kinds = [f'a {method}' for method in unread]
                shown += (f', and {" and ".join([", ".join(kinds[:-1]), kinds[-1]] if len(kinds) > 1 else kinds)} that '
                          f'{"is" if len(kinds) == 1 else "are"} not read may reject more')
            found.setdefault((path, schema_of(pair), shown), []).append(pair.start_point.row + 1)
    return found


def field_lines(graph, name, written):
    """`show Model.field` (4.6): the functions that read its model (`MapHandle.queries`; model-level, as the facts
    keep only a read's filter keys) or, in SQL, its table (`MapHandle.sql_reads`), the callers one level up of each
    function that writes it (an edge guessed by a name alone left out) and the test files whose imports reach a file
    that writes it (file-level facts)."""
    model = name.partition('.')[0]
    tables = {row.get('table') or model for row in written} or {model}
    reads = [*graph.queries(model), *(row for table in sorted(tables) for row in graph.sql_reads(table))]
    lines = [f'reads {model} {row["file"]}:{row["line"]} {row["function"]} ({row["method"]})' for row in reads]
    for function in dict.fromkeys(row_function(row) for row in written if not row.get('unclear')):
        for caller in graph.callers(function, 1, guessed=False):
            node = graph.node(caller) or {}
            lines.append(f'caller of {function.partition(":")[2] or function}: {caller.partition(":")[2] or caller}'
                         + (f' ({node["file"]}:{node["line"]})' if node.get('file') else ''))
    files = sorted({row['file'] for row in written})
    lines.extend(f'test {file} reaches a writer of {name}' for file in graph._tests_for(files, set()))
    return lines
