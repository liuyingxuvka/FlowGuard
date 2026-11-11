"""Owners and copies: one owner per judgment or field, and what this change does to the rest.

A function owner (`# flowguard: owner NAME`) is the reference its same-name sensors follow; the
existing same-name comparison checks those. Copy discovery runs unregistered look-alikes on the
owner's case classes, through the runtime's one call-site replay (`Runtime._replay_rows`), only in
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
import importlib
import inspect
import threading
import time

from flowguard.map.common import git_blob, is_test_file, read_source

SIMILAR_SHAPE = 0.5          # 3-gram Jaccard of two function bodies that counts as a similar structure
SIMILAR_FOREIGN = 0.8        # the same for JS/TS, whose copies are found by structure alone (no replay)
TRIVIAL = {0, 1, -1, 2}      # numbers too common to tie two functions together
TIMEOUT = 2.0                # seconds for one function's replay before it is listed as unclear
PEERS = 40                   # look-alikes of one changed function replayed at most, the most similar first


@dataclass
class Findings:
    """Red lines and leads for the existing signal report, each with the next step to copy."""
    red: list = field(default_factory=list)
    leads: list = field(default_factory=list)
    stats: dict = field(default_factory=dict)
    issues: list = field(default_factory=list)      # health.Issue: open structure problems, old ones too
    section: list = field(default_factory=list)     # the --all listing of open structure problems
    summary: dict | None = None                     # count and heaviest names for the session brief

    def extend(self, other):
        self.red.extend(other.red)
        self.leads.extend(other.leads)
        self.issues.extend(other.issues)
        for key, value in other.stats.items():
            self.stats[key] = self.stats.get(key, 0) + value
        return self


# ---- the change: baseline commit, changed files and their facts at the baseline ---------------------

class Change:
    """The working tree against one baseline commit, read once; no baseline means nothing is new."""

    def __init__(self, cfg, graph, baseline):
        self.cfg, self.graph, self.baseline = cfg, graph, baseline
        self.files = set(graph._git_changed(baseline)) if baseline else set()
        self._modules = {path: module for path, module in graph.con.execute('SELECT path, module FROM file')}
        self._texts, self._facts, self._impact = {}, {}, None

    def impact(self):
        """The map's changed, added and removed ids against the baseline (read once)."""
        if self._impact is None:
            self._impact = self.graph.impact(since=self.baseline) if self.baseline else dict(changed=[], added=[], removed=[])
        return self._impact

    def touched(self):
        """Functions (named, nested callbacks folded into them) this change edits or adds."""
        if not hasattr(self, '_touched'):
            impact = self.impact()
            self._touched = {named(ident) for ident in [*impact.get('changed', ()), *impact.get('added', ())]}
        return self._touched

    def writes(self):
        """Every write row of the map, read once per check; Python right sides are not folded (the structure
        checks ask who writes; a JS/TS or SQL row keeps the literal values its source spells)."""
        if not hasattr(self, '_writes'):
            self._writes = self.graph.writes(by_name=True, fold=False)
        return self._writes

    def old_text(self, file):
        if file not in self._texts:
            raw = git_blob(self.cfg.root, self.baseline, file) if self.baseline else None
            self._texts[file] = raw.decode('utf-8-sig', errors='replace') if raw is not None else None
        return self._texts[file]

    def old_facts(self, file):
        """The map facts the same extractor reads from the file's baseline bytes ({} when it was absent)."""
        if file not in self._facts:
            from flowguard.structure.extract import extract
            raw = git_blob(self.cfg.root, self.baseline, file) if self.baseline else None
            module = self._modules.get(file)
            self._facts[file] = extract(self.cfg.root, file, raw, module, is_test_file(file)) if raw is not None and module else {}
        return self._facts[file]

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


def owner_writes(change, index, *, everything=False):
    """A write outside a data owner's writers that this change adds is red; older ones are the old ledger."""
    found = Findings()
    for owner in (a for a in index.entries if a.kind == 'owner' and a.writers):
        rows = [row for row in change.graph.writes(owner.name, by_name=True) if not row.get('unclear')]
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
        where = f'{owner.file}:{owner.line}'
        if new:
            functions = '、'.join(dict.fromkeys(row['node'] if row.get('language', 'python') == 'python' else row['function']
                                                for row in new))     # TS/JS writers are function names
            found.red.append(f'new write outside the declared writer for {owner.name}：' + '  '.join(_write_text(row) for row in new)
                             + f'; allowed only: {allowed} -> call {allowed}, or, if necessary, add {functions} to '
                               f'the writers agreement (comment at {where}）')
        if old and everything:
            found.leads.append(f'before: {owner.name} writes outside the declared writer: ' + '  '.join(_write_text(row) for row in old)
                               + f'; allowed only: {allowed}(agreement at {where}）')
    return found


def _call_tree(graph, node, depth=3, up=0):
    """{named function: how}: the function and what it calls, down `depth` levels (first `up` levels of
    callers, with `up`); JS/TS member calls are resolved by name ('name')."""
    tree = {}
    for ident, how in graph.call_tree(node, depth, up=up).items():
        key = named(ident)
        tree[key] = 'name' if 'name' in (how, tree.get(key)) else how
    return tree


OPERATION = 'the same operation (3 caller levels, then 3 callee levels)'


def operation(graph, node):
    """{named function: how} of the operation a function belongs to: its callers three levels up and what
    each of them calls three levels down, so a caller that writes one field through one helper and its
    partner through another is one operation. Pairs and deletes read the same tree."""
    return _call_tree(graph, node, 3, up=3)


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


def owner_pairs(change, index, *, everything=False):
    """`with=`: each write of a registered field also writes its partner in the same operation (`operation`:
    callers three levels up, then three levels down from them), unless its function is listed in `alone=`;
    `on=update` holds only the writes that change a row (`on=create` only those that make one, `creates`).
    A test's fixture write is not held to the pair. Red when this change adds the write or the rule."""
    from .health import Issue
    found = Findings()
    def bound(row):         # a JS/TS `obj.f = ...` matched by field name alone is not a write of a model
        return not row.get('unclear') and not (row.get('how') == 'name' and row.get('language', 'python') != 'python')
    tests = {path for (path,) in change.graph.con.execute('SELECT path FROM file WHERE is_test = 1')}
    for owner in (a for a in index.entries if a.kind == 'owner' and a.pairs):
        rows = [row for row in change.graph.writes(owner.name, by_name=True) if bound(row)
                and row['file'] not in tests and not is_test_file(row['file'])
                and (not owner.on or creates(row) == (owner.on == 'create'))]
        alone = [item.partition('(')[0] for item in owner.alone]
        new_rule = change.baseline and not _owner_at_baseline(change, owner)
        for pair in owner.pairs:
            target, _, value = pair.partition('=')
            model, _, column = target.rpartition('.')
            partners = {row_function(row) for row in change.graph.writes(model if column == '*' else target, by_name=True)
                        if bound(row) and _holds(row, value or None)}
            missing, calls = [], {}
            for row in rows:
                if _allowed(row, alone):
                    continue
                tree = operation(change.graph, row_function(row))
                if not tree.keys() & partners:
                    missing.append(row)
                    calls[id(row)] = 'name' in tree.values() or row.get('language', 'python') != 'python'
            def where(rows):
                return '  '.join(f'{row["file"]}:{row["line"]} {row["function"]}' for row in rows) \
                    + ('(JS/TS calls resolved by name)' if any(calls[id(row)] for row in rows) else '') \
                    + {'update': '(updates only)', 'create': '(creates only)'}.get(owner.on, '')
            step = (f'write the paired value; if intentionally independent, ask the owner before adding except=path:function(reason) to the together agreement (comment at {owner.file}:{owner.line})')
            shown = [row for row in missing if everything or new_rule or row['file'] in change.files]
            if shown:
                # One owner per red line: the subject names the owner, so two owners' pairs never merge into one.
                found.red.append(f'missing paired write for {owner.name}：{where(shown)} writes {owner.name}, {OPERATION} does not write {pair} → ' + step)
            if missing:
                found.issues.append(Issue(
                    f'pair:{owner.name}>{pair}', 2, f'pair {owner.name}',
                    f'missing paired write: {where(missing)} writes {owner.name}; {OPERATION} does not write {pair}',
                    step, frozenset(row_function(row) for row in missing), frozenset(row['file'] for row in missing),
                    new=bool(shown)))
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
    source, never run."""
    from .runtime import _functions
    out = _foreign_constant_changes(change)
    for file in change.changed_python():
        old = change.old_text(file)
        if old is None:
            continue
        try:
            old_tree, new_tree = ast.parse(old), ast.parse(read_source(change.cfg.root / file))
        except SyntaxError:
            continue
        module = change._modules[file]
        before, after = _module_literals(old_tree), _module_literals(new_tree)
        for name in before.keys() & after.keys():
            for old_value, new_value in _differences(before[name][0], after[name][0]):
                out.append(dict(name=name, before=old_value, after=new_value, file=file, line=after[name][1],
                                identity=module + ':' + name, target=''))
        old_functions, new_functions = dict(_functions(old_tree)), dict(_functions(new_tree))
        for qual in old_functions.keys() & new_functions.keys():
            a, b = old_functions[qual], new_functions[qual]
            first = [node for node in ast.walk(a) if isinstance(node, ast.Constant)]
            second = [node for node in ast.walk(b) if isinstance(node, ast.Constant)]
            if len(first) != len(second) or _shape(a) != _shape(b):
                continue
            for x, y in zip(first, second):
                for old_value, new_value in _differences(x.value, y.value):
                    out.append(dict(name=qual + ' constant', before=old_value, after=new_value, file=file, line=y.lineno,
                                    identity='', target=module + ':' + qual))
    return out


def _shape(function):
    import copy

    class Blank(ast.NodeTransformer):
        def visit_Constant(self, node):
            return ast.copy_location(ast.Constant(type(node.value).__name__), node)
    return ast.dump(Blank().visit(copy.deepcopy(function)), include_attributes=False)


def _rule_declarations(cfg):
    """The rules in the intent folder, read from source and never run: for each file its path and tree,
    and for each rule its id, predicate node, anchor names and `.rows(...)` calls."""
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
        found.append((path, list(rules.values())))
    return found


def rule_old_values(cfg, old):
    """Rules in the intent folder whose predicate or literal rows still spell an old value."""
    kind = _value_kind(old)
    if kind is None:
        return []
    def holds(node):
        return isinstance(node, ast.Constant) and _value_kind(node.value) == kind and node.value == old
    found = []
    for path, rules in _rule_declarations(cfg):
        for item in rules:
            node = item['node']
            body = node.body[1:] if ast.get_docstring(node) is not None else node.body
            judged = sorted({n.lineno for s in body for n in ast.walk(s) if holds(n)})
            rows = sorted({n.lineno for call in item['rows'] for n in ast.walk(call) if holds(n)})
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
    rules = [(path, item) for path, items in _rule_declarations(change.cfg) for item in items if item['anchors']]
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
    return found


def old_value_leads(change):
    """Each replaced value that other decisions and rules still spell; a lead, not a verdict."""
    from .signals import stale_copies
    found = Findings()
    for item in constant_changes(change):
        lead = stale_copies(change.graph, [item])
        if lead['total']:
            found.leads.append(lead)
        found.leads.extend(rule_old_values(change.cfg, item['before']))
    if found.leads:
        from .deprecation import warn
        warn('old-value leads')
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
    of them (`check --all` lists all)."""
    found = Findings()
    named = [(name, items, ' -> keep one definition and reference it elsewhere; use different names if intentionally different') for name, items in _declarations(change.graph).items()]
    fields = [(name, items, ' -> add missing values; mark an unused description or remove it') for name, items in change.graph.field_declarations().items()]
    for name, items, step in sorted(named + fields):
        if len(items) < 2 or len({values for _, _, values in items}) < 2:
            continue
        if not everything and not any(file in change.files for file, _, _ in items):
            continue
        union = set().union(*(values for _, _, values in items))
        parts = [f'{file}:{line}（{" | ".join(map(repr, sorted(values, key=repr)))}'
                 + (f'; missing {", ".join(map(repr, sorted(union - values, key=repr)))}' if union - values else '') + '）'
                 for file, line, values in sorted(items)]
        found.leads.append(('before: ' if everything and not any(file in change.files for file, _, _ in items) else '')
                           + f'declarations differ: {name} ' + '  '.join(parts) + step)
    return found


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
    before = {row['value'] for file in change.files for row in change.old_facts(file).get('literals', ())}
    before |= {row['value'] for group in groups for rows in group['spellings'].values() for row in rows
               if row['file'] not in change.files}
    reported = False
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
        reported = True
    if reported:
        from .deprecation import warn
        warn('label-spelling leads')
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


def changed_once(change, decided=()):
    """A changed function whose baseline body (the fingerprint without name and docstring) an unchanged
    function still has: the copy this edit probably also needed. Static; `check` compares behavior. A member
    of a copies family the owner decided (`[structure."copies:a+b"]`; `decided` holds the member functions of
    each such health.copies issue as it stood at the baseline, the code the owner decided on) does not count
    the other members of that family; a function of the same name outside it (a method, an exact copy the
    family leaves out) still counts."""
    from flowguard.structure.readers.registry import ECMA, language_for
    from flowguard.structure.store import shape_list
    found = Findings()
    foreign = sorted(file for file in change.files if language_for(file) in ECMA and not is_test_file(file)
                     and file in change._modules)
    files = change.changed_python() + foreign
    if not files:
        return found
    delta = change.graph._delta_against(change.baseline, files)
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
        twins = [item for item in twins if item[0] not in fellows]          # the owner decided this family
        similar = [item for item in similar if item[0] not in fellows]
        if twins or similar:
            name = ident.partition(':')[2].rpartition('.')[2].strip('_').upper()
            comment = '//' if similar or language_for(node.get('file') or '') in ECMA else '#'
            parts = ([f'previously identical copies: {len(twins)} unchanged: ' + '  '.join(f'{file}:{line}' for _, file, line in twins)] if twins else []) \
                + ([f'similar structure (shape similarity at least {SIMILAR_FOREIGN:g}): {len(similar)} also unchanged: '
                    + '  '.join(f'{file}:{line}' for _, file, line in similar)] if similar else [])
            found.leads.append(f'{ident.partition(":")[2]}({node.get("file")}:{node.get("line")}) changed; ' + '; '.join(parts)
                               + f'(update them together when required; to lock them, write above the reference: {comment} flowguard: same {name} ref, '
                                 f'above the copy: {comment} flowguard: same {name})')
    if found.leads:
        from .deprecation import warn
        warn('similar-implementation leads')
    return found


def static_findings(cfg, graph, index, base=None, *, everything=False, replay=False, excluded=()):
    """The one assembly of owner and structure findings. Without replay (pytest, `check --static`): owner
    writes and pairs, values outside declared sets, old values (rules too), new spellings, unchanged copies
    of a changed function's old body, deletes that leave children, missing columns and the open structure
    problems (`health`). `replay` (`check`) runs copy discovery and the changed-alone comparison instead
    of the static copy lead. `everything` adds the old ledger and the `--all` structure listing."""
    from . import health
    from .ledger import structure_decisions
    change = Change(cfg, graph, baseline(cfg, base))
    copies = health.copies(change, index)
    found = owner_writes(change, index, everything=everything).extend(owner_pairs(change, index, everything=everything))
    found.extend(health.values(change, everything=everything))
    if change.baseline:
        found.extend(old_value_leads(change))
        found.extend(copies_without_rule(change, index))
        if not replay:
            decisions = structure_decisions(cfg)[0]
            # A decided family as it stood at the baseline; one this task made (no problem of that name then) as it
            # stands now, so the owner's decision on the problem the change just raised holds too.
            decided = []
            if any(name.startswith('copies:') for name in decisions):
                then = health.copies(change, index, before=True).issues
                named = {issue.name for issue in then}
                decided = [issue.nodes for issue in then if issue.name in decisions] + [
                    issue.nodes for issue in health.copies(change, index).issues
                    if issue.name in decisions and issue.name not in named]
            found.extend(changed_once(change, decided))
    if change.baseline or everything:
        found.extend(literal_drift(change, everything=everything))
    found.extend(health.deletes(change, everything=everything)).extend(health.columns(change, everything=everything))
    found.extend(health.delete_rules(change))
    found.extend(copies).extend(health.writers(change, index)).extend(health.uncreated(change))
    found.extend(health.labels(change))
    if replay:
        found.extend(discover(cfg, graph, index, change, everything=everything, excluded=excluded))
        found.extend(changed_alone(cfg, graph, index, change, excluded=excluded))
    found = health.assess(cfg, change, index, found, everything=everything)
    if everything:
        from .ledger import open_legacy
        found.section.extend(open_legacy(cfg, graph))
    return found


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


def _load(cfg, module, qual):
    """The live function object; an import that fails is a reason, the run continues without it."""
    from .config import setup_path
    from .imports import prepare
    setup_path(cfg)
    prepare(cfg.root)
    try:
        value = importlib.import_module(module)
        for part in qual.split('.'):
            value = getattr(value, part)
    except (ImportError, SyntaxError, OSError, ArithmeticError, LookupError, ValueError, TypeError,
            AttributeError, NameError, RuntimeError, AssertionError) as error:
        return None, f'import failed: {type(error).__name__}: {error}'
    if not inspect.isfunction(value):
        return None, f'{module}:{qual} is not an ordinary function'
    return value, ''


def _replay(runtime, function, rows, names, label, seconds=None):
    """Outcomes of `function` on each row, through the runtime's call-site replay; (outcomes, reason)."""
    from . import sites
    seconds = TIMEOUT if seconds is None else seconds
    from .runtime import _PRIVATE
    fn = sites.unwrap(function)
    signature = inspect.signature(fn)
    parameters = [p for p in signature.parameters.values()
                  if p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)]
    if len(parameters) != len(names) or len(parameters) != len(signature.parameters):
        return None, 'parameter counts differ'
    try:
        bound = signature.bind(*(rows[0][name] for name in names))
    except TypeError as error:
        return None, f'arguments cannot be bound: {error}'
    axes = {}
    for parameter, name in zip(parameters, names):
        pool = axes.setdefault(parameter.name, [])
        for row in rows:
            if not any(repr(row[name]) == repr(value) for value in pool):
                pool.append(row[name])
    token = _PRIVATE.set(True)
    start = len(runtime.readings)
    try:
        with watchdog(seconds):
            runtime._replay_rows(fn, bound, owner=fn, name=label, axes=axes)
    except _Timeout:
        return None, f'exceeded {seconds:g} seconds without completion'
    finally:
        _PRIVATE.reset(token)
    reading = runtime.readings[start] if len(runtime.readings) > start else None
    if reading is None or reading.status != 'ok':
        return None, '; '.join(reading.reasons) if reading else 'no replay reading'
    by_inputs = {tuple(repr(inputs[p.name]) for p in parameters): value for inputs, value in reading.rows}
    outcomes = []
    for row in rows:
        signature_key = tuple(repr(row[name]) for name in names)
        if signature_key not in by_inputs:
            return None, 'replay skipped a representative value'
        outcomes.append(by_inputs[signature_key])
    old = {tuple(repr(inputs[p.name]) for p in parameters): before for inputs, before, _ in reading.changed}
    previous = [old.get(tuple(repr(row[name]) for name in names), outcome) for row, outcome in zip(rows, outcomes)]
    return dict(now=outcomes, before=previous, compared=reading.comparison_status == 'ok'), ''


def _same(left, right):
    """Equal outcomes; raised outcomes agree by exception type, whatever their messages say."""
    from .cells import Raised
    from .runtime import outcome_equal
    if isinstance(left, Raised) or isinstance(right, Raised):
        return isinstance(left, Raised) and isinstance(right, Raised) and type(left.error) is type(right.error)
    return outcome_equal(left, right)


def _show(value):
    from .cells import Raised, show
    return f'raised {type(value.error).__name__}' if isinstance(value, Raised) else show(value)


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
                 if not _same(mine[index], reference[index])]
    finite = [item for item in differing if all(not (type(item[0][n]) is float and not math.isfinite(item[0][n])) for n in names)]
    chosen = finite[:1] + [item for item in differing if item not in finite][:1]
    text = '；'.join(', '.join(f'{name}={_show(row[name])}' for name in names) + f' → {_show(a)}({label} returns {_show(b)}）'
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
    rows, trees = [], {}
    tool = Path(__file__).resolve().parents[1]          # the running FlowGuard package never replays itself
    for ident, file, module, qual, line, end, blob in graph.con.execute(
            "SELECT n.id, n.file, n.module, n.qual, n.line, n.end_line, n.shape FROM node n JOIN file f ON f.path = n.file "
            "WHERE n.kind = 'function' AND f.is_test = 0 AND n.file LIKE '%.py' ORDER BY n.id"):
        path = (cfg.root / file).resolve()
        if '.' in qual or path.is_relative_to(cfg.intent) or path.is_relative_to(tool):
            continue                    # a nested function has no importable name of its own
        if file not in trees:
            try:
                trees[file] = dict(definitions(ast.parse(read_source(cfg.root / file))))
            except (SyntaxError, OSError, UnicodeError):
                trees[file] = {}
        node = trees[file].get(qual)
        if node is None:
            continue
        if (file, '') not in trees:
            trees[(file, '')] = _module_literals(ast.parse(read_source(cfg.root / file)))
        rows.append(dict(id=ident, file=file, module=module, qual=qual, line=line, end=end or line,
                         shape=set(shape_list(blob) if isinstance(blob, bytes) else blob or ()), node=node,
                         constants=_numbers(node), simple=_simple_parameters(node),
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
    from .ledger import structure_decisions
    from .runtime import Runtime
    found = Findings()
    decisions = structure_decisions(cfg)[0]
    owners = [a for a in index.entries if a.kind == 'sensor' and a.owner and a.source_role == 'production' and not a.issues]
    if not owners:
        return found
    started = time.perf_counter()
    functions = _functions(graph, cfg)
    by_id = {row['id']: row for row in functions}
    registered = {a.target for a in index.entries if a.kind == 'sensor'} | set(excluded)
    added = set(change.impact()['added']) if change.baseline else set()
    runtime = Runtime(cfg.root, previous={})
    candidates_seen = 0
    for owner in owners:
        home = by_id.get(owner.target)
        if home is None:
            continue
        old_owner = _owner_at_baseline(change, owner)
        names = [p.name for p in owner.parameters]
        candidates = [row for row in _look_alikes(functions, home, registered) if len(row['simple']) == len(names)]
        new_owner = change.baseline and not old_owner
        shown = [row for row in candidates if everything or new_owner or row['id'] in added
                 or row['file'] in change.files]
        candidates_seen += len(candidates)
        if not shown:
            continue
        # One row set for all: the owner's classes, fixed representatives and every compared function's literals.
        rows, kinds, reason = _classes(cfg, owner, list(dict.fromkeys(
            value for row in (home, *shown) for value in row['literals'])))
        label = f'{owner.name}（{owner.file}:{owner.target_line}）'
        if reason:
            found.leads.append(f'reference {label} suspected copy {len(shown)} copies were not compared: {reason}')
            continue
        fn, why = _load(cfg, owner.module, owner.qual)
        reference, why = _replay(runtime, fn, rows, names, owner.name) if fn else (None, why)
        if reference is None:
            found.leads.append(f'reference {label} cannot run itself; copies were not compared: {why}')
            continue
        groups, unclear = {}, []
        for row in shown:
            fn, why = _load(cfg, row['module'], row['qual'])
            result, why = _replay(runtime, fn, rows, names, owner.name) if fn else (None, why)
            if result is None:
                unclear.append(f'{row["file"]}:{row["line"]}（{why}）')
                continue
            outcomes = result['now']
            same = sum(_same(a, b) for a, b in zip(outcomes, reference['now']))
            category = _category(same, len(rows), _similarity(row['shape'], home['shape']), bool(row['constants'] & home['constants']))
            if category is None:
                continue
            # Grouped by the first difference from the owner in the fixed representative order.
            first = next(((index, _show(a)) for index in _order(rows, names)
                          for a, b in [(outcomes[index], reference['now'][index])] if not _same(a, b)), None)
            groups.setdefault((category, first), []).append((row, outcomes))
        seconds = time.perf_counter() - started
        total = sum(len(group) for group in groups.values()) + len(unclear)
        if not total:
            continue
        quiet = f'copies:{owner.name}' in decisions
        lead = found.leads.append if not quiet else (lambda text: None)
        lead(f'reference {label} has {total} suspected copies (candidates: {len(candidates)}; time: {seconds:.2f} seconds; '
                           f'{len(rows)} representative values; compared on all reference values; call-site reachability of negative, non-finite and other values was not checked)'
                           f'-> choose one for each copy: call the reference; or write above the copy: # flowguard: same {owner.name}；'
                           f'or declare distinct("{owner.name}", "<copy-anchor-name>", why="...", source="...")')
        order = {'copy': 0, 'diverged copy': 1, 'similar': 2}
        for (category, _), group in sorted(groups.items(), key=lambda item: (order[item[0][0]], item[1][0][0]['id'])):
            members = [row for row, _ in group]
            places = '  '.join(f'{row["file"]}:{row["line"]}' for row in members)
            if category == 'copy':
                text = f'{category}: {len(members)} copies (match the reference on {len(rows)} representative values; not a proof): {places}'
            else:
                apart = len({tuple(_show(value) for value in outcomes) for _, outcomes in group}) > 1
                text = (f'{category} {len(members)} copies: {_example(rows, names, group[0][1], reference["now"])}：{places}'
                        + ('(same first difference; these copies also differ on other representative values)' if apart else ''))
            fresh = [row for row in members if row['id'] in added]
            if fresh and old_owner and category != 'similar':
                found.red.append(f'reference {label} has a new copy outside it: ' + '  '.join(f'{row["file"]}:{row["line"]}' for row in fresh)
                                 + f'({category}) -> call {owner.qual}, or write above it: # flowguard: same {owner.name}')
            lead(('before: ' if everything and not new_owner and not fresh else '') + text)
            if category == 'diverged copy':
                from .health import Issue
                found.issues.append(Issue(f'copies:{owner.name}', 5, f'copy {owner.name}', f'reference {label}: {text}',
                                          f'choose one for each copy: call {owner.qual}; or write # flowguard: same {owner.name} above the copy and make it agree; '
                                          f'or declare distinct("{owner.name}", "<copy-anchor-name>", why="...", source="...")',
                                          frozenset({owner.target, *(row['id'] for row in members)}),
                                          frozenset({owner.file, *(row['file'] for row in members)})))
        if unclear:
            lead(f'unavailable copies: {len(unclear)} copies: ' + '  '.join(unclear))
    found.stats.update(copy_candidates=candidates_seen, copy_seconds=time.perf_counter() - started)
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
    from .runtime import Runtime
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
    runtime = Runtime(cfg.root, change.baseline)
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
        fn, why = _load(cfg, row['module'], row['qual'])
        if fn is None:
            continue
        mine, why = _replay(runtime, fn, rows, row['simple'], row['qual'])
        if mine is None or not mine['compared'] or all(_same(a, b) for a, b in zip(mine['before'], mine['now'])):
            continue            # no comparable old version, or the edit kept every representative's result
        examined += 1
        twins, similar = [], []
        for peer in peers:
            other, why = _load(cfg, peer['module'], peer['qual'])
            theirs, why = _replay(runtime, other, rows, row['simple'], peer['qual']) if other else (None, why)
            if theirs is not None and all(_same(a, b) for a, b in zip(mine['before'], theirs['now'])):
                if not all(_same(a, b) for a, b in zip(mine['now'], theirs['now'])):
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
        name = anchor.name if anchor else row['qual'].strip('_').upper()
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
        else:
            found.leads.append(text + f'(update them together when required; to lock them, write above the reference: # flowguard: same {name} ref, '
                                      f'above the copy: # flowguard: same {name})')
    found.stats.update(changed_examined=examined, changed_seconds=time.perf_counter() - started)
    if found.leads:
        from .deprecation import warn
        warn('similar-implementation leads')
    return found


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
    opened, _ = health.decided(cfg, index, [*static.issues, *found.issues])
    found.summary = health.summary(opened)
    if everything:
        from .ledger import open_legacy
        found.section = health.section(opened) + open_legacy(cfg, graph)
    return found


def show_lines(cfg, graph, index, name):
    """`show NAME` of an owner: its writers and the writes outside them, or its unregistered look-alikes."""
    lines = []
    for owner in index.named(name):
        if owner.kind == 'owner' and owner.writers:
            rows = [row for row in graph.writes(owner.name, by_name=True)]
            outside = [row for row in rows if not row.get('unclear') and not _allowed(row, owner.writers)]
            lines.append(f'owner {owner.name} {owner.file}:{owner.line}; writers={",".join(owner.writers)}')
            def plain(row):
                value = f', value {row["value"]!r}' if 'value' in row else ''
                return f'{row["file"]}:{row["line"]} {row["function"]} ({row["kind"]}{value})'
            lines.extend('outside writers: ' + plain(row) for row in outside)
            lines.extend('unclear: ' + plain(row) + f' {row.get("reason", "")}' for row in rows if row.get('unclear'))
            lines.extend(f'with {pair}' for pair in owner.pairs)
            lines.extend(f'alone {item}' for item in owner.alone)
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
