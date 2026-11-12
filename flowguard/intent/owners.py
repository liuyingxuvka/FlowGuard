"""Owners and copies: one owner per judgment or field, and what this change does to the rest.

A function owner (`# flowguard: owner NAME`) is the reference its same-name sensors follow; the
existing same-name comparison checks those. Copy discovery runs unregistered look-alikes on the
owner's case classes, through the runtime's source-only sealed executor, only in
`check`. A data owner (`owner Table.column writers=...`) turns a new write outside its writers red.
Static leads (an old value still elsewhere, also in rules; a new spelling of a label) never replay.
Only what this change adds is reported; older findings are the old ledger (`check --all`, `show`).
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

from flowguard.map.common import git_blob, git_run, is_test_file, read_source, sha256_bytes

SIMILAR_SHAPE = 0.5          # 3-gram Jaccard of two function bodies that counts as a similar structure
SIMILAR_FOREIGN = 0.8        # the same for JS/TS, whose copies are found by structure alone (no replay)
TRIVIAL = {0, 1, -1, 2}      # numbers too common to tie two functions together
TIMEOUT = 2.0                # seconds for one function's replay before it is listed as unclear
PEERS = 40                   # look-alikes of one changed function replayed at most, the most similar first


@dataclass
class Findings:
    """Red lines and leads for the existing signal report, each with the next step to copy; and, for the 4.3
    lines (`signals.deliver`), the findings with their members, the lines already of their kind, what this change
    touches and which families ran."""
    red: list = field(default_factory=list)
    leads: list = field(default_factory=list)
    stats: dict = field(default_factory=dict)
    issues: list = field(default_factory=list)      # health.Issue: open structure problems, old ones too
    section: list = field(default_factory=list)     # the --all listing of open structure problems
    summary: dict | None = None                     # count and heaviest names for the session brief
    known: list = field(default_factory=list)       # sources.Known: the entries of known.toml, sites resolved
    lines: list = field(default_factory=list)       # signals.Line of their final kind (impact, loosened, not compared)
    hidden: list = field(default_factory=list)      # {feature, text}: leads that get no line, only `show --last`
                                                    # (feature: the 5.0-deprecated heuristic; '' for none)
    ran: set = field(default_factory=set)           # the families whose checks judged the whole project in this run
                                                    # (a known entry's `known fixed?`; `families_ran`)
    touched_functions: frozenset = frozenset()      # what this change edits or adds: a finding's member there is
    touched_files: frozenset = frozenset()          # touched (`deliver`); files for a file-level member
    decided: list = field(default_factory=list)     # the issues a `[structure]` decision closed (counted, no line)

    def extend(self, other):
        self.red.extend(other.red)
        self.leads.extend(other.leads)
        self.issues.extend(other.issues)
        self.known.extend(other.known)
        self.lines.extend(other.lines)
        self.hidden.extend(other.hidden)
        self.ran |= other.ran
        self.touched_functions |= other.touched_functions
        self.touched_files |= other.touched_files
        self.decided.extend(other.decided)
        for key, value in other.stats.items():
            self.stats[key] = self.stats.get(key, 0) + value
        return self


def _ascii(text):
    """A legacy FlowGuard text with its full-width punctuation written in ASCII (project names stay as they are)."""
    for wide, plain in (('\u3001', ', '), ('\uff1b', '; '), ('\uff1a', ': '), ('\uff08', ' ('), ('\uff09', ')'), ('\uff0c', ', '),
                        ('\u2192', '->')):
        text = text.replace(wide, plain)
    return text


def _hide(found, feature, text):
    """Keep a lead that gets no 4.3 line for `show --last` (D6): `feature` names the 5.0-deprecated heuristic. FlowGuard
    makes these leads itself, so they print no `deprecated:` notice: a notice says that the project's own input (a
    comment spelling, a declaration, a command option) uses a feature that goes in 5.0."""
    found.hidden.append(dict(feature=feature, text=_ascii(text)))


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

    def decisions(self):
        """The ledger's `[structure]` decisions (`ledger.structure_decisions`), read once for every check of this change:
        the section is a 5.0-deprecated feature, and each read prints its deprecation line."""
        from .ledger import structure_decisions
        return self.held('structure decisions', lambda: structure_decisions(self.cfg)[0])

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
        once per check (the touched functions and the changed-once leads both ask)."""
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
        staged with `git mv`; an untracked file is no rename to Git). Read once."""
        if not hasattr(self, '_renamed'):
            self._renamed = {}
            if self.baseline:
                listed = git_run(self.graph.root, 'diff', '-M', '--name-status', '-z', '--relative', self.baseline, '--').stdout
                parts = [os.fsdecode(part) for part in listed.split(b'\0')]
                at = 0
                while at < len(parts) and parts[at]:
                    status = parts[at]
                    if status[:1] in ('R', 'C'):
                        if status[:1] == 'R':
                            self._renamed[parts[at + 1]] = parts[at + 2]
                        at += 3
                    else:
                        at += 2
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

    def baseline_definitions(self):
        """The value sets, constants and schema models of the baseline (`graph.definitions`): those of each path of
        `baseline_paths` read from its baseline facts, the map's for every other file. Built once."""
        if self._definitions is None:
            self._definitions = self.graph.definitions(
                [(path, self.module(path), self.old_facts(path)) for path in sorted(self.baseline_paths())])
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
                facts += [record for record in map(self.old_facts, sorted(paths)) if record]
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

    def rule_declarations(self):
        """The intent source facts of this change, not an old-value matching result."""
        if not hasattr(self, '_rules'):
            self._rules = _rule_declarations(self.cfg)
        return self._rules

    def changed_python(self):
        return sorted(file for file in self.files if file.endswith('.py') and file in self._modules
                      and not is_test_file(file) and not (self.cfg.root / file).resolve().is_relative_to(self.cfg.intent))


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
    for writer in writers:
        if ':' in writer:
            if row['node'] == writer:
                return True
        elif row['function'] == writer or row['function'].endswith('.' + writer):
            return True
    return False


def _write_key(row):
    return row['file'], row['function'], row['kind'], str(row.get('model') or row.get('table')), str(row.get('field') or row.get('db_column'))


def _write_text(row):
    value = f', value {row["value"]!r}' if 'value' in row else ''
    return f'{row["file"]}:{row["line"]} {row["function"]}（{row["kind"]}{value}）'


def _agreement_place(graph, owner, role):
    """A role's original declaration, before complementary data agreements were combined."""
    facts = graph.file_facts(owner.file)
    rows = [row for row in facts.get('anchors', ()) if row['kind'] == 'owner' and row['name'] == owner.name
            and not row['qual'] and row.get(role)] if facts is not None else []
    if len(rows) == 1:
        return f'{owner.file}:{rows[0]["line"]}'
    return f'canonical registration {owner.file}:{owner.line}'


def owner_writes(change, index, *, everything=False):
    """A write outside a data owner's writers that this change adds is red; older ones are the old ledger."""
    found, written = Findings(ran={'writer'}), None
    for owner in (a for a in index.entries if a.kind == 'owner' and a.writers):
        if written is None:
            written = change.graph.writes(by_name=True)        # read once for every owner
        rows = [row for row in change.graph.writes_to(written, owner.name) if not row.get('unclear')]
        outside = [row for row in rows if not _allowed(row, owner.writers)]
        if not outside:
            continue
        before = Counter()
        for file in {row['file'] for row in outside} & change.files:
            facts = change.old_facts(file)
            if facts:
                before.update(_write_key(row) for row in change.graph.writes(owner.name, by_name=True, facts=[facts])
                              if not row.get('unclear'))
        now, new, old = Counter(_write_key(row) for row in outside), [], []
        for row in outside:
            key = _write_key(row)
            fresh = change.baseline and row['file'] in change.files and now[key] > before[key]
            (new if fresh else old).append(row)
        allowed = '、'.join(owner.writers)
        where = _agreement_place(change.graph, owner, 'writers')
        if new:
            functions = '、'.join(dict.fromkeys(row['node'] if row.get('language', 'python') == 'python' else row['function']
                                                for row in new))     # TS/JS writers are function names
            found.red.append(f'new write outside the declared writer for {owner.name}：' + '  '.join(_write_text(row) for row in new)
                             + f'; allowed only: {allowed} -> call {allowed}, or, if necessary, add {functions} to '
                               f'the writers agreement (comment at {where}）')
        if old and everything:
            found.leads.append(f'before: {owner.name} writes outside the declared writer: ' + '  '.join(_write_text(row) for row in old)
                               + f'; allowed only: {allowed}(agreement at {where}）')
        found.issues.append(_writer_issue(change, owner, outside, where))
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
    return writer.rpartition(':')[2] if ':' in writer else writer


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
                 step, frozenset(now), frozenset(row['file'] for row in outside), new=bool(fresh),
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


def owner_pairs(change, index, *, everything=False):
    """`with=` (`together A B`): each write of a registered field also writes its partner in the same operation
    (`operation`: callers three levels up, then three levels down from them; a JS/TS module-level callback is an
    operation of its own), unless its function is listed in `alone=`; `on=update` holds only the writes that change
    a row (`on=create` only those that make one, `creates`). A partner of the trigger's own function holds it only
    for the same record (`_same_record`), and a conditional partner field only under the trigger's own condition
    (`_unconditional`). A test's fixture write is not held to the pair.

    One `pair:A>B` finding per agreement and partner, one part per function that misses it (`_pair_function`).
    A part is fresh (this change added it) unless the baseline result has it: the current registration applied to
    the baseline code (the writes of every changed file at the baseline, `Change.baseline_writes`, a module-level
    callback by its counterpart), judged with the current operation tree, and only while that tree lost no call the
    baseline had (`_Calls`; else the part is fresh, fail-closed). Without a baseline nothing is fresh. The legacy red
    line names the misses of changed files, or every miss of an agreement this change added.

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
        new_rule = change.baseline and not _owner_at_baseline(change, owner)
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
            step = (f'write the paired value; if intentionally independent, ask the owner before adding except=path:function(reason) to the together agreement (comment at {_agreement_place(change.graph, owner, "pairs")})')
            shown = [row for row in missing if everything or new_rule or row['file'] in change.files]
            if shown:
                # One owner per red line: the subject names the owner, so two owners' pairs never merge into one.
                found.red.append(f'missing paired write for {owner.name}：{where(shown)} writes {owner.name}, {OPERATION} does not write {pair} → ' + step)
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
                new=bool(shown), family='pair', subject=f'together {owner.name}',
                parts=tuple((function, _pair_place(row), f'writes {owner.name} without {pair}{scope}', _pair_step(row, partner))
                            for function, row in members.items()),
                fresh=frozenset(fresh), detail=tuple(detail)))
    return found


# ---- static leads: old values, rules that still hold them, new spellings ------------------------------

def _value_kind(value):
    return 'number' if type(value) in (int, float) else 'text' if type(value) is str else None


def _differences(before, after):
    """(old, new) pairs of two literal values: scalars, or the members of tuples, lists and dicts."""
    if type(before) in (tuple, list) and type(after) in (tuple, list) and len(before) == len(after):
        return [pair for a, b in zip(before, after) for pair in _differences(a, b)]
    if type(before) is dict and type(after) is dict and before.keys() == after.keys():
        return [pair for key in before for pair in _differences(before[key], after[key])]
    if _value_kind(before) and _value_kind(before) == _value_kind(after) and before != after:
        return [(before, after)]
    return []


_UNREADABLE = object()


def _module_literals(tree):
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


def _foreign_constant_changes(change):
    """The same for JS/TS files, from the map's facts: `const NAME = literal` constants and the decision
    literals (comparisons, cases, returns, sets, unions) of a function whose shape is otherwise unchanged."""
    from flowguard.structure.readers.registry import ECMA, language_for
    out = []
    for file in sorted(change.files):
        if language_for(file) not in ECMA or is_test_file(file) or (new := change.graph.file_facts(file)) is None:
            continue
        old = change.old_facts(file)
        if not old:
            continue
        from flowguard.structure.store import shape_list
        module = change._modules[file]
        nodes = [dict(qual=qual, kind=kind, sig=sig, line=line, shape=shape_list(blob) if isinstance(blob, bytes) else list(blob or ()))
                 for qual, kind, sig, line, blob in change.graph.con.execute(
                     'SELECT qual, kind, sig, line, shape FROM node WHERE file = ?', (file,))]
        before = {node['qual']: node for node in old['nodes'] if node['kind'] == 'const'}
        for node in nodes:
            previous = before.get(node['qual'])
            if node['kind'] != 'const' or previous is None:
                continue
            (a, first), (b, second) = _literal_text(previous['sig']), _literal_text(node['sig'])
            for old_value, new_value in _differences(first, second) if a and b else ():
                out.append(dict(name=node['qual'], before=old_value, after=new_value, file=file, line=node['line'],
                                identity=module + ':' + node['qual'], target=''))
        shapes = {node['qual']: list(node.get('shape') or ()) for node in old['nodes']}
        now_shapes = {node['qual']: node['shape'] for node in nodes}
        def by_function(facts):
            rows = {}
            for row in sorted([*facts.get('literals', ()), *facts.get('numbers', ())], key=lambda row: (row['line'], row['column'])):
                rows.setdefault(named(row['node']), []).append(row)
            return rows
        old_rows, new_rows = by_function(old), by_function(new)
        for ident in old_rows.keys() & new_rows.keys():
            qual = ident.partition(':')[2]
            first, second = old_rows[ident], new_rows[ident]
            if not qual or len(first) != len(second) or shapes.get(qual) != now_shapes.get(qual):
                continue
            for x, y in zip(first, second):
                for old_value, new_value in _differences(x['value'], y['value']):
                    out.append(dict(name=qual + ' constant', before=old_value, after=new_value, file=file, line=y['line'],
                                    identity='', target=ident))
    return out


def _literal_text(text):
    """(readable, value) of a constant's source text; a JS/TS constant that is no literal takes no part in
    old-value leads."""
    from .cache import _literal
    value = _literal(text, _UNREADABLE)
    return (False, None) if value is _UNREADABLE else (True, value)


def constant_changes(change):
    """Literal values this change replaced: module constants (also inside tuples and dicts) and the
    constants of a function whose structure is otherwise unchanged, in Python and JS/TS files. Read from
    source, never run; each source text's constants are read once (`_source_constants`)."""
    out = _foreign_constant_changes(change)
    for file in change.changed_python():
        blob = change.graph._baseline_object(change.baseline, file)
        if blob is None:
            continue
        try:
            new = read_source(change.cfg.root / file)
            old_facts = _source_constants(change.graph, ['blob', blob], lambda: change.old_text(file))
            new_facts = _source_constants(change.graph, ['text', sha256_bytes(new.encode('utf-8', 'surrogatepass'))], lambda: new)
        except SyntaxError:
            continue
        module = change._modules[file]
        before, after = old_facts['literals'], new_facts['literals']
        for name in before.keys() & after.keys():
            for old_value, new_value in _differences(before[name][0], after[name][0]):
                out.append(dict(name=name, before=old_value, after=new_value, file=file, line=after[name][1],
                                identity=module + ':' + name, target=''))
        old_functions, new_functions = old_facts['functions'], new_facts['functions']
        for qual in old_functions.keys() & new_functions.keys():
            a, b = old_functions[qual], new_functions[qual]
            if a['text'] == b['text']:
                continue                    # the same lines: decorators, signature and body
            first, second = a['constants'], b['constants']
            if len(first) != len(second):
                continue
            differences = [(line, _differences(x, y)) for (_, x), (line, y) in zip(first, second)]
            if not any(pairs for _, pairs in differences) or a['shape'] != b['shape']:
                continue
            for line, pairs in differences:
                for old_value, new_value in pairs:
                    out.append(dict(name=qual + ' constant', before=old_value, after=new_value, file=file, line=line,
                                    identity='', target=module + ':' + qual))
    return out


CONSTANT_FACTS = 1          # the form of `_read_constants`; a new form never reads an older one


def _source_constants(graph, source, text):
    """The constants of one Python source text (`_read_constants`), read once per text and kept with the map's
    other rebuildable facts. `source` names the text: a baseline blob, or the digest of a working-tree text;
    `text()` gives it when it was not read before. A text that does not parse raises SyntaxError and is not kept.
    Facts only: the comparison of two texts is never stored. The key holds the digest of the code that reads
    the facts (this file and `runtime._functions`'s, as `reader_digest` does for the map's readers) and of
    `structure/store.py`, whose `pack` format they are stored in, so an upgraded FlowGuard never reuses facts
    an earlier version stored."""
    import json
    import sys
    from pathlib import Path
    from flowguard.map.common import content_digest
    from flowguard.structure import store
    if 'constant_facts_code' not in graph._derived:
        from . import runtime
        graph._derived['constant_facts_code'] = [content_digest(Path(__file__)), content_digest(Path(runtime.__file__)),
                                                 content_digest(Path(store.__file__))]
    identity = json.dumps([*source, CONSTANT_FACTS, sys.implementation.cache_tag, *graph._derived['constant_facts_code']],
                          separators=(',', ':'))
    key = 'constant_facts:' + sha256_bytes(identity.encode())
    held = graph._derived.setdefault('constant_facts', {})
    if key not in held:
        row = graph.con.execute('SELECT v FROM meta WHERE k=?', (key,)).fetchone()
        if row is None:
            packed = store.pack(_read_constants(text()))
            active = graph.con.in_transaction
            from .cache import put_meta
            put_meta(graph.con, key, packed)
            if not active:
                graph.con.commit()
        else:
            packed = row[0]
        facts = store.unpack(packed)
        held[key] = dict(literals={name: (_unpacked(value), line) for name, value, line in facts['literals']},
                         functions={qual: dict(text=text_digest, shape=shape, constants=[(line, _unpacked(value)) for line, value in constants])
                                    for qual, text_digest, shape, constants in facts['functions']})
    return held[key]


def _read_constants(text):
    """What constant_changes compares in one source text: its module literals (`_module_literals`, in their
    order) and, for each function `_functions` finds, the digest of its lines (decorators to last line), the
    digest of its structure with constants reduced to their type (`_shape_key`) and its constants in
    `ast.walk` order."""
    from .runtime import _functions
    tree = ast.parse(text)
    lines = text.split('\n')
    functions = []
    for qual, node in dict(_functions(tree)).items():
        start = min([node.lineno, *(d.lineno for d in node.decorator_list)]) - 1
        span = lines[start:node.end_lineno]
        functions.append([qual, sha256_bytes(_json_text([len(span), *span]).encode('utf-8', 'surrogatepass')),
                          sha256_bytes(_shape_key(node).encode('utf-8', 'surrogatepass')),
                          [[part.lineno, _packed(part.value)] for part in ast.walk(node) if isinstance(part, ast.Constant)]])
    return dict(literals=[[name, _packed(value), line] for name, (value, line) in _module_literals(tree).items()],
                functions=functions)


def _json_text(value):
    import json
    return json.dumps(value, ensure_ascii=False, separators=(',', ':'))


def _packed(value):
    """A literal value in a JSON form that keeps its exact type (`_unpacked` reads it back)."""
    kind = type(value)
    if value is None or value is Ellipsis:
        return [repr(value)]
    if kind is bool or kind is str:
        return [kind.__name__, value]
    if kind is int:
        return ['int', hex(value)]
    if kind is float:
        return ['float', value.hex()]
    if kind is complex:
        return ['complex', value.real.hex(), value.imag.hex()]
    if kind is bytes:
        return ['bytes', value.hex()]
    if kind in (tuple, list, set):
        return [kind.__name__, [_packed(part) for part in value]]
    if kind is dict:
        return ['dict', [[_packed(key), _packed(part)] for key, part in value.items()]]
    raise TypeError('a literal of type ' + kind.__name__ + ' has no stored form')


def _unpacked(data):
    kind = data[0]
    if kind in ('None', 'Ellipsis'):
        return None if kind == 'None' else Ellipsis
    if kind in ('bool', 'str'):
        return data[1]
    if kind == 'int':
        return int(data[1], 16)
    if kind == 'float':
        return float.fromhex(data[1])
    if kind == 'complex':
        return complex(float.fromhex(data[1]), float.fromhex(data[2]))
    if kind == 'bytes':
        return bytes.fromhex(data[1])
    if kind in ('tuple', 'list', 'set'):
        return {'tuple': tuple, 'list': list, 'set': set}[kind](_unpacked(part) for part in data[1])
    if kind == 'dict':
        return {_unpacked(key): _unpacked(part) for key, part in data[1]}
    raise ValueError('unknown stored literal form ' + repr(kind))


_ABSENT = object()


def _shape_key(function):
    """A function's structure with each constant reduced to its type name, as one text (the same comparison
    as `ast.dump` of that reduced tree): every part is written with its length, so two structures share a key
    only when they are the same. Built without recursion, so a deep expression cannot exhaust the stack."""
    parts, stack = [], [function]
    while stack:
        item = stack.pop()
        if type(item) is str:
            parts.append(f'{len(item)}:{item}')
            continue
        if isinstance(item, ast.Constant):
            stack.append('C' + type(item.value).__name__)
            continue
        fields = ['N' + type(item).__name__]
        for name in item._fields:
            value = getattr(item, name, _ABSENT)
            # As ast.dump: a missing field and a None one whose class default is None are both left out.
            if value is _ABSENT or value is None and getattr(type(item), name, ...) is None:
                fields.append('-')
            elif type(value) is list:
                fields.append('[' + str(len(value)))
                fields.extend(part if isinstance(part, ast.AST) else 'v' + repr(part) for part in value)
            elif isinstance(value, ast.AST):
                fields.append(value)
            else:
                fields.append('v' + repr(value))
        stack.extend(reversed(fields))
    return ''.join(parts)


def _rule_declarations(cfg):
    """The rules in the intent folder, read from source and never run: for each file its path and tree,
    and for each rule its id, predicate node, anchor names, `.rows(...)` calls and the constants of both."""
    if not cfg.intent.is_dir():
        return []
    found = []
    for path in sorted(cfg.intent.rglob('*.py')):
        try:
            tree = ast.parse(path.read_text(encoding='utf-8-sig'))
        except (SyntaxError, UnicodeError):
            continue        # the loader reports a rule file it cannot read
        rules = {}
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for decorator in node.decorator_list:
                name = decorator.func.attr if isinstance(decorator, ast.Call) and isinstance(decorator.func, ast.Attribute) \
                    else decorator.func.id if isinstance(decorator, ast.Call) and isinstance(decorator.func, ast.Name) else ''
                if name == 'rule':
                    arguments = [*decorator.args, *(k.value for k in decorator.keywords if k.arg == 'id')]
                    identifier = arguments[0].value if arguments and isinstance(arguments[0], ast.Constant) else node.name
                    anchor = next((k.value for k in decorator.keywords if k.arg == 'anchor'), None)
                    named = [anchor] if isinstance(anchor, ast.Constant) else list(getattr(anchor, 'elts', ()))
                    line = min([node.lineno, *(item.lineno for item in node.decorator_list)])  # as the loader counts it
                    rules[node.name] = dict(id=identifier, node=node, line=line, rows=[],
                                            anchors=[item.value for item in named if isinstance(item, ast.Constant)
                                                     and isinstance(item.value, str)])
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == 'rows' \
                    and isinstance(node.func.value, ast.Name) and node.func.value.id in rules:
                rules[node.func.value.id]['rows'].append(node)
        for item in rules.values():
            # The constants rule_old_values compares with each old value: the predicate's (docstring aside)
            # and those of its literal rows, collected once.
            node = item['node']
            body = node.body[1:] if ast.get_docstring(node) is not None else node.body
            item['judged'] = [n for s in body for n in ast.walk(s) if isinstance(n, ast.Constant)]
            item['literals'] = [n for call in item['rows'] for n in ast.walk(call) if isinstance(n, ast.Constant)]
        found.append((path, list(rules.values())))
    return found


def rule_old_values(cfg, old, *, declarations=None):
    """Rules in the intent folder whose predicate or literal rows still spell an old value."""
    kind = _value_kind(old)
    if kind is None:
        return []
    def holds(node):
        return isinstance(node, ast.Constant) and _value_kind(node.value) == kind and node.value == old
    found = []
    for path, rules in _rule_declarations(cfg) if declarations is None else declarations:
        for item in rules:
            judged = sorted({n.lineno for n in item['judged'] if holds(n)})
            rows = sorted({n.lineno for n in item['literals'] if holds(n)})
            if judged or rows:
                parts = ([f'decision line {"、".join(map(str, judged))}'] if judged else []) + \
                        ([f'regression row line {"、".join(map(str, rows))}'] if rows else [])
                found.append(f'rule {item["id"]} still uses old value {old!r}({cfg.rel(path)} {"、".join(parts)}): if requirements changed, update the rule first')
    return found


def copies_without_rule(change, index):
    """A changed function that is a rule's anchor or one of its same-name copies, in a change that does not
    touch that rule's file: the requirement may have changed without its rule. A lead with both next steps.
    Changed means its body, a constant it reads or a function it calls changed against the baseline."""
    found = Findings()
    rules = [(path, item) for path, items in change.rule_declarations() for item in items if item['anchors']]
    if not change.baseline or not rules:
        return found
    impact = change.impact()
    moved = set(impact['dirty']) | set(impact['callers'])
    copies = {}
    for anchor in index.entries:
        if anchor.kind == 'sensor' and anchor.source_role == 'production' and anchor.target in moved:
            copies.setdefault(anchor.name, []).append(anchor)
    for path, item in rules:
        file = change.cfg.rel(path)
        changed = [anchor for name in item['anchors'] for anchor in copies.get(name, ())]
        if not changed or file in change.files:
            continue
        names = '、'.join(dict.fromkeys(anchor.name for anchor in changed))
        places = '、'.join(dict.fromkeys(f'{anchor.file}:{anchor.qual}' for anchor in changed))
        found.leads.append(f'{names} copies at {places} changed; rule {item["id"]} is unchanged -> if requirements changed, first use python -m flowguard req add to '
                           f'store the new owner words, then update rule {file}:{item["line"]}; otherwise confirm that this code change is correct')
        _hide(found, '', found.leads[-1])         # no 4.3 line and no deprecation (D6): `show --last` only
    return found


def _old_value_text(lead):
    """The text of an old-value lead (`signals.stale_copies`) for `show --last`."""
    def shown(value):
        return repr(value) if isinstance(value, str) else str(value)
    values = ', '.join(dict.fromkeys(shown(row['old']) for row in lead['locations']))
    return (f'old values {values} remain in {lead["total"]} decisions: '
            + '  '.join(f'{row["file"]}:{row["line"]}' + (' (in a large function)' if row.get('big') else '') for row in lead['locations'])
            + ' -> if requirements changed, update them together')


def old_value_leads(change):
    """Each replaced value that other decisions and rules still spell; a lead, not a verdict."""
    from .signals import stale_copies
    found = Findings()
    for item in constant_changes(change):
        lead = stale_copies(change.graph, [item])
        if lead['total']:
            found.leads.append(lead)
            _hide(found, 'old-value leads', _old_value_text(lead))
        for text in rule_old_values(change.cfg, item['before'], declarations=change.rule_declarations()):
            found.leads.append(text)
            _hide(found, 'old-value leads', text)
    return found


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


def declarations_differ(change, *, everything=False):
    """Two declarations of one name (union type or enum) with different members, and the declarations of one
    database field (`MapHandle.field_declarations`: each Prisma schema's enum, each SQL CHECK, a JS/TS
    declaration of the enum's name) with different values: a lead, reported when this change touches one
    of them (`check --all` lists all). Each is also a `declarations:` finding of the files declaring it, new when a
    file declares that name otherwise than the baseline code did (`_declared`)."""
    found = Findings()
    found.ran.add('declarations')
    named = [(name, items, ' -> keep one definition and reference it elsewhere; use different names if intentionally different') for name, items in _declarations(change.graph).items()]
    fields = [(name, items, ' -> add missing values; mark an unused description or remove it') for name, items in change.graph.field_declarations().items()]
    field_names = {name for name, _, _ in fields}
    for name, items, step in sorted(named + fields):
        if len(items) < 2 or len({values for _, _, values in items}) < 2:
            continue
        found.issues.append(_declarations_issue(change, name, items, step.removeprefix(' -> '), field=name in field_names))
        if not everything and not any(file in change.files for file, _, _ in items):
            continue
        union = set().union(*(values for _, _, values in items))
        parts = [f'{file}:{line}（{" | ".join(map(repr, sorted(values, key=repr)))}'
                 + (f'; missing {", ".join(map(repr, sorted(union - values, key=repr)))}' if union - values else '') + '）'
                 for file, line, values in sorted(items)]
        found.leads.append(('before: ' if everything and not any(file in change.files for file, _, _ in items) else '')
                           + f'declarations differ: {name} ' + '  '.join(parts) + step)
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
                 step, frozenset(), files, new=fresh, family='declarations', subject=f'declarations {name}',
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


def literal_drift(change, *, everything=False):
    """A label spelled a new way (case, spaces, punctuation aside) that this change adds to a group of
    spellings: only a spelling the baseline code never used is reported. Two declarations of one name
    with different members are part of the same lead family."""
    found = declarations_differ(change, everything=everything)
    if not change.files and not everything:
        return found
    groups = _project_spellings(change, change.graph.literal_groups())
    if not groups:
        return found
    before = {row['value'] for file in change.files for row in change.old_part(file, 'literals') or ()}
    before |= {row['value'] for group in groups for rows in group['spellings'].values() for row in rows
               if row['file'] not in change.files}
    for group in groups:
        fresh = [value for value in group['spellings'] if value not in before]
        if not fresh and not everything:
            continue
        parts = []
        for value, rows in group['spellings'].items():
            places = '、'.join(f'{row["file"]}:{row["line"]}' for row in rows)
            parts.append(f'{value!r}({places}' + (', spelling added in this task' if value in fresh else '') + ')')
        # --all also lists the spellings the baseline already had, as the old ledger.
        found.leads.append(('' if fresh else 'before: ') + 'label spellings differ: ' + ' and '.join(parts)
                           + ' -> use one spelling, or read both from one reference')
        _hide(found, 'label-spelling leads', found.leads[-1])
    return found


def _project_spellings(change, groups):
    """The label groups without the spellings of FlowGuard's own generated files (`init` writes '-3', '-c',
    '--root' into them), keeping the groups that still have two spellings."""
    from .config import init_generated
    own = {}
    def project(row):
        if row['file'] not in own:
            path = change.cfg.root / row['file']
            own[row['file']] = not (path.is_file() and init_generated(path))
        return own[row['file']]
    kept = []
    for group in groups:
        spellings = {value: [row for row in rows if project(row)] for value, rows in group['spellings'].items()}
        spellings = {value: rows for value, rows in spellings.items() if rows}
        if len(spellings) >= 2:
            kept.append(dict(group, spellings=spellings))
    return kept


def changed_once(change, decided=(), index=None):
    """A changed function whose baseline body (the fingerprint without name and docstring) an unchanged
    function still has: the copy this edit probably also needed. Static; `check` compares behavior. A member
    of a copies family the owner decided (`[structure."copies:a+b"]`; `decided` holds the member functions of
    each such health.copies issue as it stood at the baseline, the code the owner decided on) does not count
    the other members of that family; a function of the same name outside it (a method, an exact copy the
    family leaves out) still counts. A copy registered with the changed function as copies of one same name
    (`index`, the flowguard comments) is not counted either: that name's comparison already covers them, and
    the lead never asks to register what is registered (`_lock_hint`)."""
    from flowguard.structure.readers.registry import ECMA, language_for
    from flowguard.structure.store import shape_list
    found = Findings()
    registered = {anchor.target: anchor.name for anchor in index.entries if anchor.kind == 'sensor'} if index is not None else {}
    foreign = sorted(file for file in change.files if language_for(file) in ECMA and not is_test_file(file)
                     and file in change._modules)
    files = change.changed_python() + foreign
    if not files:
        return found
    delta = change.delta(files)
    touched = {row[0] for row in delta}
    shapes = None
    for ident, kind, old_fp, new_fp, _, _ in delta:
        if kind != 'changed' or not old_fp or '<anonymous' in ident:
            continue
        twins = [(other, file, line) for other, file, line in change.graph.con.execute(
            "SELECT id, file, line FROM node WHERE fp = ? AND kind IN ('function', 'method') ORDER BY id", (old_fp,))
            if other not in touched]
        node = change.graph.node(ident) or {}
        similar = []
        if language_for(node.get('file') or '') in ECMA:
            # JS/TS functions cannot be run here: structure alone (the 3-gram shape before the edit) finds them.
            if shapes is None:
                shapes = [(other, file, line, set(shape_list(blob) if isinstance(blob, bytes) else blob or ()))
                          for other, file, line, blob in change.graph.con.execute(
                              "SELECT id, file, line, shape FROM node WHERE kind IN ('function', 'method') AND shape IS NOT NULL")
                          if language_for(file or '') in ECMA and not is_test_file(file or '')]
            qual = ident.partition(':')[2]
            old_shape = set(next((item.get('shape') or () for item in change.old_facts(node['file']).get('nodes', ())
                                  if item['qual'] == qual), ()))
            known = {other for other, _, _ in twins}
            similar = [(other, file, line) for other, file, line, shape in shapes
                       if other not in touched and other not in known and old_shape and shape
                       and len(old_shape & shape) / len(old_shape | shape) >= SIMILAR_FOREIGN]
        fellows = set().union(*(members for members in decided if ident in members))
        own = registered.get(ident)
        # the owner decided this family; copies registered with this function are compared as that name
        twins = [item for item in twins if item[0] not in fellows and not (own and registered.get(item[0]) == own)]
        similar = [item for item in similar if item[0] not in fellows and not (own and registered.get(item[0]) == own)]
        if twins or similar:
            marked = [registered[other] for other in (ident, *(item[0] for item in [*twins, *similar])) if other in registered]
            name = marked[0] if marked else ident.partition(':')[2].rpartition('.')[2].strip('_').upper()
            comment = '//' if similar or language_for(node.get('file') or '') in ECMA else '#'
            parts = ([f'previously identical copies: {len(twins)} unchanged: ' + '  '.join(f'{file}:{line}' for _, file, line in twins)] if twins else []) \
                + ([f'similar structure (shape similarity at least {SIMILAR_FOREIGN:g}): {len(similar)} also unchanged: '
                    + '  '.join(f'{file}:{line}' for _, file, line in similar)] if similar else [])
            found.leads.append(f'{ident.partition(":")[2]}({node.get("file")}:{node.get("line")}) changed; ' + '; '.join(parts)
                               + _lock_hint(comment, name, bool(marked)))
            _hide(found, 'similar-implementation leads', found.leads[-1])
    return found


def _counted(number, noun, plural=None):
    """`1 reader`, `2 readers`, `1 copy`, `3 copies`: a count with its noun in the number it needs."""
    return f'{number} ' + (noun if number == 1 else plural or noun + 's')


def _lock_hint(comment, name, marked):
    """How a similar-implementation lead says to register its copies as copies of `name`: the reference and the copy
    when neither is registered yet, else only the copies not marked (`marked`: one of them is registered already)."""
    if marked:
        return f'(update them together when required; to lock them, write above each copy not marked yet: {comment} flowguard: same {name})'
    return (f'(update them together when required; to lock them, write above the reference: {comment} flowguard: same {name} ref, '
            f'above the copy: {comment} flowguard: same {name})')


# ---- what this change loosened, and the fields it newly writes (4.3) ----------------------------------

LOOSENED_STEP = "name it in your report; needs the owner's yes"


def _agreements(rows, moved=None):
    """The agreements of these `anchors` fact rows: {field: {'writers': {writer: row}, 'pairs': {partner: row},
    'alone': {function: row}, 'on': {on: row}}} of the data agreements (writers, together; the old owner spellings
    are the same rows), and {(name, function): [rows]} of the same-name copies (`same`, `same NAME ref`, a function
    owner). A position is the function it resolves to (`module:function`; a bare name of the old owner spelling,
    which any file's function of that name satisfies, stays bare), so a comment moved to another file means the
    function of that file it now names; `moved` maps the module of a file renamed away to its new module."""
    moved = moved or {}

    def resolved(position):
        target, colon, qual = position.rpartition(':')
        return moved.get(target, target) + colon + qual if colon else position
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
        elif row['kind'] in ('sensor', 'owner'):
            same.setdefault((row['name'], resolved(row['module'] + ':' + row['qual'])), []).append(row)
    return data, same


def _moved_modules(change, paths, current):
    """{old module: new module} of the files this change renames: those Git reports renamed (`Change.renamed`, a
    staged rename), and a file deleted beside one added whose comments (`current`, {path: anchors rows}) are the
    baseline file's, up to the file and module they name (a file moved without Git, its comments with it)."""
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
        if path not in change._modules and module and module not in moved and (rows := change.old_part(path, 'anchors')):
            gone.setdefault(shape(rows, module), []).append(module)
    added = {}
    for path in sorted(change.files - set(change.renamed().values())):
        if current.get(path) and change.old_text(path) is None:
            added.setdefault(shape(current[path], change._modules[path]), []).append(change._modules[path])
    for key, modules in gone.items():
        if len(modules) == 1 and len(added.get(key, ())) == 1:
            moved[modules[0]] = added[key][0]
    return moved


def loosened(change, index):
    """What this change loosened in the agreements of its `flowguard:` comments (D9), each a `loosened` line: an
    `except=` (`alone=`) added, also in a new together; a together partner removed (the whole agreement too); an
    `on=` added to or changed in a together that stays; a writer added to a writers agreement that stays; a writers
    agreement removed; a `same NAME` removed from a function. The baseline's comments are the old `anchors` facts of
    the files this change edits, deletes or renames away, beside the map's for every other file. Positions compare
    as the functions they resolve to, a renamed file's by its new module (`_moved_modules`): a comment moved beside
    another function of the name it spells now names that function. A file moved without Git and edited in its
    comments too is a file deleted and one added."""
    from .signals import Line
    found = Findings()
    paths = change.baseline_paths() if change.baseline else frozenset()
    if not paths:
        return found
    old_rows, new_rows, current = [], [], {}
    for path, _, data in change.graph._kinds('anchors'):
        new_rows.extend(data.get('anchors', ()))
        current[path] = data.get('anchors', ())
        if path not in paths:
            old_rows.extend(data.get('anchors', ()))
    for path in sorted(paths):
        old_rows.extend(change.old_part(path, 'anchors') or ())
    moved = _moved_modules(change, paths, current)
    (then, same_then), (now, same_now) = _agreements(old_rows, moved), _agreements(new_rows)
    files = {change.module(path): path for path in paths if change.module(path)} | {module: path for path, module in change._modules.items()}

    def spelled(position, row):
        """A position as the comment at `row` spells it: a function of its own file bare, another's path:function."""
        target, colon, qual = position.rpartition(':')
        return qual if not colon or target == row['module'] else f'{files.get(target, target)}:{qual}'

    def line(key, text, row, function=''):
        place = f'{row["file"]}:{row["line"]}'
        found.lines.append(Line('loosened', f'loosened:{key}', function, text, LOOSENED_STEP, (place,), (f'comment at {place}',)))

    for name in sorted(then.keys() | now.keys()):
        old, new = then.get(name), now.get(name)
        if new is not None:
            for exception in sorted(new['alone'].keys() - (old['alone'].keys() if old else set())):
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
                for writer in sorted(new['writers'].keys() - old['writers'].keys()):
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
    from .health import _test_files, decided, written_field, writers
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
            open_writers = {issue.name for issue in decided(change.cfg, index, writers(change, index).issues, change.decisions())[0]}
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


def static_findings(cfg, graph, index, base=None, *, everything=False, replay=False, excluded=()):
    """The one assembly of owner and structure findings. Without replay (pytest, `check --static`): owner
    writes and pairs, values outside declared sets, old values (rules too), new spellings, unchanged copies
    of a changed function's old body, deletes that leave children, missing columns and the open structure
    problems (`health`). `replay` (`check`) runs copy discovery and the changed-alone comparison instead
    of the static copy lead. `everything` adds the old ledger and the `--all` structure listing. The catalog's
    findings (`sources.findings`), what the change loosened and the fields it newly writes join the same list."""
    from . import health, sources
    change = Change(cfg, graph, baseline(cfg, base))
    copies = health.copies(change, index)
    found = owner_writes(change, index, everything=everything).extend(owner_pairs(change, index, everything=everything))
    found.extend(sources.findings(cfg, graph, change))
    found.extend(loosened(change, index))
    found.extend(field_impact(change, index))
    found.extend(health.values(change, everything=everything))
    if change.baseline:
        found.extend(old_value_leads(change))
        found.extend(copies_without_rule(change, index))
        if not replay:
            decisions = change.decisions()
            # A decided family as it stood at the baseline; one this task made (no problem of that name then) as it
            # stands now, so the owner's decision on the problem the change just raised holds too.
            decided = []
            if any(name.startswith('copies:') for name in decisions):
                then = change.held('copies before', lambda: health.copies(change, index, before=True)).issues
                named = {issue.name for issue in then}
                decided = [issue.nodes for issue in then if issue.name in decisions] + [
                    issue.nodes for issue in copies.issues if issue.name in decisions and issue.name not in named]
            found.extend(changed_once(change, decided, index))
    if change.baseline or everything:
        found.extend(literal_drift(change, everything=everything))
    found.extend(health.deletes(change, everything=everything)).extend(health.columns(change, everything=everything))
    found.extend(health.delete_rules(change))
    found.extend(copies).extend(health.writers(change, index)).extend(health.uncreated(change))
    found.extend(health.labels(change))
    if replay:
        found.extend(discover(cfg, graph, index, change, everything=everything, excluded=excluded))
        found.extend(changed_alone(cfg, graph, index, change, excluded=excluded))
    found = families_ran(health.assess(cfg, change, index, found, everything=everything), index)
    found.ran.add('pair')
    found.touched_functions, found.touched_files = touched_functions(change), frozenset(change.files)
    if everything:
        from .ledger import open_legacy
        found.section.extend(open_legacy(cfg, graph))
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
    text = '；'.join(', '.join(f'{name}={_show(row[name])}' for name in names) + f' → {_outcome(a)}({label} returns {_outcome(b)}）'
                    for row, a, b in chosen)
    return text + (f'; plus {len(differing) - len(chosen)} other differences' if len(differing) > len(chosen) else '')


def _kind_of(value):
    from .cells import Kind
    return Kind({float: 'float', int: 'int'}.get(type(value), 'dec' if type(value).__name__ == 'Decimal' else 'other'))


# ---- copy discovery against a registered function owner ----------------------------------------------

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


def _category(same, total, shape, shared):
    if same == total:
        return 'copy'
    if 2 * same >= total and shape >= SIMILAR_SHAPE:
        return 'diverged copy'
    return 'similar' if shared else None


def discover(cfg, graph, index, change, *, everything=False, excluded=()):
    """Unregistered look-alikes of each function owner, grouped by their results on its classes. An owner
    whose copies the owner decided (`[structure."copies:NAME"]`, NAME its anchor name) gets no leads; a copy
    this change adds beside it is still red."""
    found = Findings()
    decisions = change.decisions()
    owners = _references(index)
    if not owners:
        return found
    started = time.perf_counter()
    functions = _functions(graph, cfg)
    by_id = {row['id']: row for row in functions}
    registered = {a.target for a in index.entries if a.kind == 'sensor'} | set(excluded)
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
        label = f'{owner.name}（{owner.file}:{owner.target_line}）'
        if reason:
            found.leads.append(f'reference {label} suspected copy {len(shown)} copies were not compared: {reason}')
            _hide(found, 'unregistered copy discovery', found.leads[-1])
            complete = False
            continue
        reference, why = _replay(home, rows, names)
        if reference is None:
            found.leads.append(f'reference {label} cannot run itself; copies were not compared: {why}')
            _hide(found, 'unregistered copy discovery', found.leads[-1])
            complete = False
            continue
        groups, unclear, partial = {}, [], []
        for row in shown:
            result, why = _replay(row, rows, names)
            if result is None:
                unclear.append(f'{row["file"]}:{row["line"]}（{why}）')
                continue
            outcomes = result['now']
            compared = [_same(a, b) for a, b in zip(outcomes, reference['now']) if _same(a, b) is not None]
            if missing := _not_compared(outcomes, reference['now']):
                partial.append(f'{row["file"]}:{row["line"]} ({missing})')
            if not compared:
                unclear.append(f'{row["file"]}:{row["line"]} (no comparable inputs)')
                continue
            category = _category(sum(compared), len(compared), _similarity(row['shape'], home['shape']), bool(row['constants'] & home['constants']))
            if category is None:
                continue
            # Grouped by the first difference from the owner in the fixed representative order.
            first = next(((index, _outcome(a)) for index in _order(rows, names)
                          for a, b in [(outcomes[index], reference['now'][index])] if _same(a, b) is False), None)
            groups.setdefault((category, first), []).append((row, outcomes))
        complete = complete and not unclear
        seconds = time.perf_counter() - started
        total = sum(len(group) for group in groups.values()) + len(unclear)
        if not total:
            continue
        quiet = f'copies:{owner.name}' in decisions
        def lead(text):
            if not quiet:
                found.leads.append(text)
                _hide(found, 'unregistered copy discovery', text)
        lead(f'reference {label} has {total} suspected copies (candidates: {len(candidates)}; time: {seconds:.2f} seconds; '
                           f'{len(rows)} representative values; only comparable JSON inputs count; call-site reachability was not checked)'
                           f'-> choose one for each copy: call the reference; or write above the copy: # flowguard: same {owner.name}；'
                           f'or declare distinct("{owner.name}", "<copy-anchor-name>", why="...", source="...")')
        order = {'copy': 0, 'diverged copy': 1, 'similar': 2}
        for (category, _), group in sorted(groups.items(), key=lambda item: (order[item[0][0]], item[1][0][0]['id'])):
            members = [row for row, _ in group]
            places = '  '.join(f'{row["file"]}:{row["line"]}' for row in members)
            if category == 'copy':
                compared_count = sum(_same(a, b) is not None for a, b in zip(group[0][1], reference['now']))
                text = f'{category}: {len(members)} copies (match the reference on {compared_count} representative values; not a proof): {places}'
            else:
                apart = len({tuple(str(value) for value in outcomes) for _, outcomes in group}) > 1
                text = (f'{category} {len(members)} copies: {_example(rows, names, group[0][1], reference["now"])}：{places}'
                        + ('(same first difference; these copies also differ on other representative values)' if apart else ''))
            fresh = [row for row in members if row['id'] in added]
            if fresh and old_owner and category != 'similar':
                found.red.append(f'reference {label} has a new copy outside it: ' + '  '.join(f'{row["file"]}:{row["line"]}' for row in fresh)
                                 + f'({category}) -> call {owner.qual}, or write above it: # flowguard: same {owner.name}')
            lead(('before: ' if everything and not new_owner and not fresh else '') + text)
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
                                          f'or declare distinct("{owner.name}", "<copy-anchor-name>", why="...", source="...")',
                                          frozenset({owner.target, *(row['id'] for row in members)}),
                                          frozenset({owner.file, *(row['file'] for row in members)}), **facts))
            elif category == 'copy' and fresh and old_owner:
                found.issues.append(Issue(f'copies:{owner.name}', LINES_ONLY, f'copy {owner.name}', f'reference {label}: {text}',
                                          f'call {owner.qual}', frozenset(row['id'] for row in members),
                                          frozenset(row['file'] for row in members), new=True, **facts))
        if unclear:
            lead(f'unavailable copies: {len(unclear)} copies: ' + '  '.join(unclear))
        if partial:
            lead('not compared: ' + '  '.join(partial))
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

def changed_alone(cfg, graph, index, change, *, excluded=()):
    """A changed function whose old version agreed with unchanged look-alikes on every representative
    value, while the new one differs: those copies probably needed the same change. Owners make it red."""
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
        peers = [other for other in functions if other['id'] not in touched and other['id'] not in excluded
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
            found.leads.append(f'not compared: {row["file"]}:{row["line"]} {row["qual"]} ({missing})')
            found.lines.append(_not_compared_line(row, missing))
        if mine is None or not mine['compared'] or not any(_same(a, b) is False for a, b in zip(mine['before'], mine['now'])):
            continue            # no comparable old version, or the edit kept every representative's result
        examined += 1
        twins, similar = [], []
        for peer in peers:
            theirs, why = _replay(peer, rows, row['simple'])
            if theirs is not None and (missing := _not_compared(mine['before'], theirs['now'])):
                found.leads.append(f'not compared: {peer["file"]}:{peer["line"]} {peer["qual"]} ({missing})')
                found.lines.append(_not_compared_line(peer, missing))
            comparison = [_same(a, b) for a, b in zip(mine['before'], theirs['now']) if _same(a, b) is not None] if theirs else []
            if comparison and all(comparison):
                if any(_same(a, b) is False for a, b in zip(mine['now'], theirs['now'])):
                    twins.append(peer)
            else:
                similar.append((peer, why if theirs is None else ''))
        if twins or similar:
            alone[row['id']] = (row, sorted(twins, key=lambda peer: peer['id']),
                                sorted(similar, key=lambda item: item[0]['id']))
    merged = {}
    for row, twins, similar in alone.values():     # several edits that left the same copies behind: one line
        key = (tuple(peer['id'] for peer in twins), tuple(peer['id'] for peer, _ in similar))
        merged.setdefault(key, (twins, similar, []))[2].append(row)
    for twins, similar, changed in merged.values():
        # The owner among the changed is the one named: its copies follow it, as the same-name red says.
        owned = [item for item in changed if item['id'] in anchored and anchored[item['id']].owner]
        row = owned[0] if owned else min(changed, key=lambda item: (len(item['qual']), item['qual']))
        anchor = anchored[row['id']] if owned else next((anchored[item['id']] for item in changed if item['id'] in anchored), None)
        if anchor:
            # a look-alike registered under the changed function's name is compared as that name: no lead names it
            similar = [(peer, why) for peer, why in similar if not (peer['id'] in anchored and anchored[peer['id']].name == anchor.name)]
            if not twins and not similar:
                continue
        marked = [anchored[peer['id']].name for peer in [*twins, *(peer for peer, _ in similar)] if peer['id'] in anchored]
        name = anchor.name if anchor else marked[0] if marked else row['qual'].strip('_').upper()
        parts = []
        if twins:
            parts.append(f'{len(twins)} previously equivalent copies are unchanged: ' + '  '.join(f'{peer["file"]}:{peer["line"]}' for peer in twins))
        if similar:
            parts.append(f'similar (structure or shared constant): {len(similar)} copies also unchanged: '
                         + '  '.join(f'{peer["file"]}:{peer["line"]}' + (f'(unavailable: {why})' if why else '') for peer, why in similar))
        text = ('、'.join(f'{item["qual"]}（{item["file"]}:{item["line"]}）' for item in changed)
                + (f' ({len(changed)} locations)' if len(changed) > 1 else '') + ' changed behavior; ' + '；'.join(parts))
        if anchor and twins:
            # The owner is the reference: its copies follow it, and a copy that left it goes back to it. Without
            # one among them no copy is chosen: an intended change goes to every copy, any other is undone.
            owner = next((peer for peer in twins if peer['id'] in anchored and anchored[peer['id']].owner
                          and anchored[peer['id']].name == anchor.name), None)
            quals = '、'.join(item['qual'] for item in changed)
            if anchor.owner:
                step = f'update together, or call {row["qual"]}'
            elif owner:
                step = f'make {quals} match reference {owner["qual"]}({owner["file"]}:{owner["line"]})'
            else:
                step = f'first decide which copy is correct: for an intended change, update together or call {row["qual"]}; otherwise make {quals} return to the original behavior'
            found.red.append(f'{"reference" if anchor.owner else "anchor"} {anchor.name}：' + text + ' → ' + step)
            found.issues.append(_changed_alone_issue(anchor, changed, twins, _ascii(step)))     # the legacy line keeps its text
        else:
            found.leads.append(text + _lock_hint('#', name, bool(anchor or marked)))
            _hide(found, 'similar-implementation leads', found.leads[-1])
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
                 frozenset(item['id'] for item in changed), frozenset(item['file'] for item in changed), new=True,
                 family='changed-alone', subject=f'same {anchor.name}', parts=parts,
                 fresh=frozenset(item['id'] for item in changed))


def check_findings(cfg, graph, index, base=None, *, everything=False, excluded=(), static=None):
    """`check`: the static findings with copy discovery and the changed-alone comparison."""
    if static is None:
        return static_findings(cfg, graph, index, base, everything=everything, replay=True, excluded=excluded)
    # Pytest already assembled the static facts. Replay remains outside its session and can add
    # copy issues; assess those and refresh the combined summary without running the static checks twice.
    from . import health
    change = Change(cfg, graph, baseline(cfg, base))
    found = discover(cfg, graph, index, change, everything=everything, excluded=excluded).extend(
        changed_alone(cfg, graph, index, change, excluded=excluded))
    found = health.assess(cfg, change, index, found)
    found = families_ran(Findings().extend(static).extend(found), index)
    opened = health.decided(cfg, index, found.issues, change.decisions())[0]
    found.summary = health.summary(opened)
    if everything:
        from .ledger import open_legacy
        found.section = health.section(opened) + open_legacy(cfg, graph)
    return found


def show_lines(cfg, graph, index, name):
    """`show NAME` of an owner: its writers and the writes outside them, or its unregistered look-alikes; and for
    a writers or together agreement the fix the red line leaves out (4.7: a red line names no way to silence it)."""
    lines = []
    for owner in index.named(name):
        if owner.kind == 'owner' and owner.writers:
            rows = [row for row in graph.writes(owner.name, by_name=True)]
            outside = [row for row in rows if not row.get('unclear') and not _allowed(row, owner.writers)]
            where = _agreement_place(graph, owner, "writers")
            lines.append(f'owner {owner.name} {where}; writers={",".join(owner.writers)}')
            def plain(row):
                value = f', value {row["value"]!r}' if 'value' in row else ''
                return f'{row["file"]}:{row["line"]} {row["function"]} ({row["kind"]}{value})'
            lines.extend('outside writers: ' + plain(row) for row in outside)
            lines.extend('unclear: ' + plain(row) + f' {row.get("reason", "")}' for row in rows if row.get('unclear'))
            lines.extend(f'with {pair}' for pair in owner.pairs)
            lines.extend(f'alone {item}' for item in owner.alone)
            if outside:
                lines.append(f'fix: call {" or ".join(dict.fromkeys(map(_writer_name, owner.writers)))} instead; only with the '
                             f"owner's yes add a function to the writers agreement ({where})")
            if owner.pairs:
                lines.append(_pair_fix(graph, owner))
        elif owner.kind == 'owner' and owner.pairs:
            lines.append(f'together {owner.name} {",".join(owner.pairs)}' + (f' on={owner.on}' if owner.on else '')
                         + f' {_agreement_place(graph, owner, "pairs")}')
            lines.extend(f'except {item}' for item in owner.alone)
            lines.append(_pair_fix(graph, owner))
        elif owner.owner:
            functions = _functions(graph, cfg)
            home = next((row for row in functions if row['id'] == owner.target), None)
            registered = {a.target for a in index.entries if a.kind == 'sensor'}
            if home is None:
                continue
            similar = _look_alikes(functions, home, registered)
            lines.append(f'owner {owner.name} {owner.file}:{owner.target_line}; {len(similar)} unregistered look-alikes '
                         '(not run here; check --all compares them)')
            lines.extend(f'look-alike {row["file"]}:{row["line"]} {row["qual"]}' for row in similar)
    return lines


def _pair_fix(graph, owner):
    return (f'fix: also write {", ".join(owner.pairs)} in the same operation; only with the owner\'s yes add '
            f'except=path:function(reason) to the together agreement ({_agreement_place(graph, owner, "pairs")}), '
            'which the next run shows as loosened')


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
