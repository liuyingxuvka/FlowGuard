"""Structure health: the map checks that need no test run, and the open structure problems they leave.

Each check reads the one map (`MapHandle.writes()`, `value_sets()`, `queries()`, `children()`,
`schema_gaps()`, `label_tables()`, `call_tree()`): a value outside its declared set, a delete that leaves
restricting children, a column one description of a table lacks, two same-name functions whose bodies differ.
Every problem, old ones too, is an `Issue` with a stable name and its members, those this change added fresh;
`signals.deliver` gives each member its line. The owner's decision in the `[structure]` section of
`.flowguard/ledger.toml` (eight words or more, sourced from stored owner words or a written rule)
closes an issue; a decision on who writes a field also needs its `owner ... writers=` anchor.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from flowguard.map.common import is_test_file

LINES_ONLY = 0               # the rank of a finding only the 4.3 lines report: no brief count
BOOKKEEPING = {'id', 'createdat', 'updatedat', 'created_at', 'updated_at', 'createdbyid', 'updatedbyid',
               'created_by', 'updated_by', 'revision', 'version'}     # written by every writer on purpose
WRITER_FILES = 3             # files writing one field without an owner before it is an issue
SIMILAR_COPY = 0.8           # shape similarity of two same-name functions that makes them copies
CREATING = ('create', 'createMany', 'createManyAndReturn', 'upsert:create', 'upsert:update', 'update', 'updateMany',
            'updateManyAndReturn', 'sql:insert', 'sql:update')   # code that makes or keeps rows of a table
DELETING = ('delete', 'deleteMany', 'nested:delete', 'nested:deleteMany', 'sql:delete')
INSERTING = ('create', 'createMany', 'createManyAndReturn', 'upsert:create', 'sql:insert')      # code that makes rows
RESTRICTING = ('NoAction', 'Restrict')
NO_KEY = 'no foreign key'       # a schema whose table has a relation's key columns but no @relation on them


@dataclass(frozen=True)
class Issue:
    """One finding (an open structure problem, and from 4.3 every other finding too): a stable name, its
    severity rank, a short name for the session brief, the problem with every place, the next step to copy,
    and the functions and files that touch it. A finding's identity is (name, the function of one part)."""
    name: str
    rank: int
    short: str
    text: str
    step: str
    nodes: frozenset = frozenset()
    files: frozenset = frozenset()
    entry: tuple = ()            # lines to copy (a ledger entry), which `show Model.field` prints after the step
    # The 4.3 lines (`signals.deliver`)
    family: str = ''             # a key of `signals.FAMILIES` ('pair', 'values', 'delete', ...)
    subject: str = ''            # what the finding is about: 'together Project.leaderId', 'same ISO_WEEKS_IN_YEAR'
    parts: tuple = ()            # one (function, place, what, red_step) per member; function '' for a file-level finding,
                                 # place 'path:symbol' (or 'path:line') relative to the repository
    fresh: frozenset = frozenset()   # the members' functions absent from the baseline result: this change added them
    detail: tuple = ()           # further lines only `show --last` and `show NAME` print


def _findings():
    from .owners import Findings
    return Findings()


def _places(rows):
    return '  '.join(dict.fromkeys(f'{row["file"]}:{row["line"]}' for row in rows))


# ---- values outside a declared set (Prisma enums, SQL CHECK, JS/TS annotated members) --------------

def _foreign_writes(change, facts=None, *, baseline=False):
    """Write rows outside Python with a readable value, keyed for the gate by `Model.field`, each with its
    file's `package` (a guessed schema's set judges only some packages) and its `scope`: the schema in use
    whose enum judges it, or the file whose declaration of a TS type judges it (None: none). `baseline` reads
    the baseline code instead (`Change.baseline_writes`, and the typed members with the baseline's own constants
    and models), scoped by the schemas and types in use now."""
    from flowguard.structure.api import _module_stem
    graph = change.graph
    # The schemas in use that define a model (schema, its package, {field: enum values}), in path order; the
    # files that declare each TS type name, and those declaring a member with each of its sets.
    models, type_files, declaring = graph.prisma_fields_in_use(), graph.ts_type_files(), {}
    for row in graph.value_sets():
        if row['kind'] == 'ts-type':
            declaring.setdefault(row['field'], []).append(row['scope'])

    def schema_of(row, key, client):
        """A typed object of one schema's client output: that schema; any other write: the schema in use of
        its own package that types the field with an enum (the nearest package defining the model), unless the
        package's clients disagree (which client wrote it is unknown): two schemas type it with different enums,
        or one with a client of its own (a generator `output`, another database) types it as text. A schema that
        lacks the field, or a template without a client of its own that types it as text (SQLite has no enums),
        neither judges nor stands in the way; when no schema of the package types it with an enum, no enum
        judges it. A package with none: the first schema in use by path whose enum types the field."""
        model, _, field = key.partition('.')
        found = [(schema, package, fields, client_of) for schema, package, fields, client_of in models.get(model, ())]
        if client in {schema for schema, _, _, _ in found}:
            return client
        for package in graph._packages_up(row['file']):
            own = [(schema, fields, client_of) for schema, owner, fields, client_of in found if owner == package]
            if own:
                enums = [(schema, fields[field]) for schema, fields, _ in own if fields.get(field)]
                apart = any(field in fields and not fields[field] and client_of for _, fields, client_of in own)
                return enums[0][0] if enums and len({values for _, values in enums}) == 1 and not apart else None
        return next((schema for schema, _, fields, _ in found if fields.get(field)), None)

    def file_of(row, gate):
        """The file whose declaration of a TS type judges a typed object: its own file when that declares the
        type's name, else the module it imports the type from by a relative path when that one does, judged only
        by a set that file declares the member with; neither: the member's only set, none when it has several."""
        sets = declaring[gate]
        files = type_files.get(row['container'], frozenset()).union(*sets)
        if row['file'] in files:
            return row['file']
        imported = next((file for file in sorted(files) if row['type_from'] and _module_stem(file) == row['type_from']), None)
        if imported is not None:
            return imported
        return sets[0][0] if len(sets) == 1 else None

    typed, definitions = facts, None
    if baseline:
        # The baseline code: every file's writes as the baseline had them, resolved by its own definitions, and
        # the typed members of the files this change leaves alone and of the baseline bytes of the others.
        paths = change.baseline_paths()
        rows = change.baseline_writes()
        typed = [data for path, _, data in graph._kinds('language', 'typed_writes', 'dependencies') if path not in paths]
        typed += [record for record in map(change.old_facts, sorted(paths)) if record]
        definitions = change.baseline_definitions()
    else:
        rows = graph.writes(facts=facts) if facts is not None else change.writes()
    out = [dict(row, field=f'{row["model"]}.{row["field"]}', values=[v for v in row.get('values', ()) if v is not None],
                scope=schema_of(row, f'{row["model"]}.{row["field"]}', None))
           for row in rows if row.get('model') and not row.get('unclear') and row.get('language', 'python') != 'python'
           and row.get('values')]
    # gated by the TS type's own sets; a type the file imports from the Prisma client by its model's sets
    # (`model`: the imported model's name, also under an alias or a namespace)
    for row in graph.typed_writes(facts=typed, definitions=definitions):
        if not row.get('values'):
            continue
        key = f'{row["model"]}.{row["field"]}'
        if row['prisma']:
            extra = dict(scope=schema_of(row, key, row['schema']))
        else:
            gate = f'ts:{row["container"]}.{row["field"]}'
            extra = dict(gate=gate, scope=file_of(row, gate) if gate in declaring else None)
        out.append(dict(row, field=key, values=[v for v in row['values'] if v is not None], **extra))
    return [dict(row, package=graph.package(row['file'])) for row in out if row['values']]


# The kinds of set in the order that takes a field's plain problem name, `values:NAME`, the name 4.1 gave the
# one problem of each field: 4.1 read every Prisma enum first (a guessed schema's too), a CHECK only for a field
# without one, and a TS type only for a name with neither.
PLAIN_FIRST = ('prisma-enum', 'sql-check', 'ts-type')


def _issue_names(sets):
    """{(gate key, where): problem name} of every declared set: one problem per set, named without line
    numbers, so a name stays put across runs and when lines move. Of the sets of one name, an enum (of a
    schema in use before a guessed one), else the CHECK, else the TS type is `values:NAME` (the first by where
    it is declared among sets of one kind); each further set adds its `place`: the schema, the CHECK's
    description (a migrations folder, `prisma/migrations/`, or the .sql file), the first TS file declaring the
    member with it, the first file of a guessed set; and its values when one file declares two sets."""
    by_name, out = {}, {}
    for row in sets:
        by_name.setdefault(row['name'], []).append(row)
    for name, rows in by_name.items():
        rows, taken = sorted(rows, key=lambda row: (PLAIN_FIRST.index(row['kind']), row['guessed'], row['place'])), set()
        for index, row in enumerate(rows):
            issue = f'values:{name}' + (f':{row["place"]}' if index else '')
            if issue in taken:
                issue += ':' + '|'.join(map(str, row['values']))
            taken.add(issue)
            out[row['field'], row['where']] = issue
    return out


def values(change):
    """A value written outside its declared set is a `values` finding, one member per function writing it; a member
    is new where its function writes that value outside the set more often than the baseline code did. One gate
    decides (`anchors.outside_sets`)."""
    from .anchors import declared_sets, outside_sets
    from .owners import place, row_function
    found = _findings()
    found.ran.add('values')
    sets = change.graph.value_sets()
    if not sets:
        return found
    names = _issue_names(sets)
    table = declared_sets((), foreign=sets)
    outside = list(outside_sets(table, _foreign_writes(change)))
    if not outside:
        return found
    key = lambda row, declared, value: (row['file'], row_function(row), row['field'], declared['where'], repr(value))
    now = Counter(key(row, declared, value) for row, declared, value in outside)
    # The 4.3 baseline (D2): the sets declared now, applied to the baseline code with its own constants and schemas.
    # A write is new when its function writes that value outside the set more often than the baseline code did; a
    # set this change narrows over writes that were already there leaves them old.
    then = None if not change.baseline else now if not change.baseline_paths() else Counter(
        key(row, declared, value) for row, declared, value in outside_sets(table, _foreign_writes(change, baseline=True)))
    by_field = {}
    for row, declared, value in outside:
        by_field.setdefault((row.get('gate', row['field']), declared['where']), (declared, []))[1].append((row, value))
    for (gate, where), (declared, items) in sorted(by_field.items()):
        name, issue_name = declared['name'], names[gate, where]
        allowed = '|'.join(map(str, declared['values']))
        text = ('Value outside the declared set: ' + '  '.join(f'{row["file"]}:{row["line"]} {name}={value!r}' for row, value in items)
                + f'; allowed {allowed} ({where})')
        step = 'use a value from the declared set; to add a value, change its declaration first (' + where + ')'
        members = {}
        for row, value in items:
            members.setdefault(row_function(row), (row, {}))[1].setdefault(repr(value), (row, declared, value))
        declared_values = '|'.join(map(repr, declared['values']))
        parts = tuple((function, place(row), 'writes ' + ', '.join(written) + f' outside {declared_values}', 'use a declared value')
                      for function, (row, written) in sorted(members.items()))
        new = frozenset(function for function, (_, written) in members.items() if then is not None
                        and any(now[key(*item)] > then[key(*item)] for item in written.values()))
        found.issues.append(Issue(issue_name, 1, f'value {name}', text, step,
                                  frozenset(row_function(row) for row, _ in items), frozenset(row['file'] for row, _ in items),
                                  family='values', subject=f'values {items[0][0]["field"]}',
                                  parts=parts, fresh=new, detail=(f'declared at {where}',)))
    return found


# ---- deletes that leave restricting children (Prisma) --------------------------------------------

def _restricts(child):
    """NoAction/Restrict, or no onDelete on a relation whose key can never be null (Prisma's default
    Restrict, also under an optional relation field; a relation whose key fields are all optional defaults
    to SetNull and does not block the delete)."""
    return child['on_delete'] in RESTRICTING or not child['on_delete'] and child['required']


def _handled(child, parent, rows, queries, back):
    """Does one of these writes or reads delete, null or count the child's rows of this parent?"""
    keys = set(child['keys']) | {child['relation']}
    for row in rows:
        if row.get('model') == child['child'] and (row['kind'] in DELETING or row['field'] in child['keys']
                                                   and None in (row.get('values') or ()) and not row.get('partial')
                                                   or row['kind'] == 'disconnect'):
            return True
    for row in queries:
        if row.get('model') == child['child'] and set(row['keys']) & keys:
            return True
        if row.get('model') == parent and ('*' in row['counts'] or set(row['counts']) & back or set(row['loads']) & back):
            return True
    return False


def deletes(change):
    """A Prisma delete of a parent whose restricting children (NoAction/Restrict) are not deleted, nulled
    or counted anywhere in the same operation: the function's callers three levels up and what they call
    three levels down (JS/TS calls resolved by name). Tables the code never creates rows in are left out, and
    so is a self relation whose parent key can be null (a tree) unless one row is deleted and code creates rows
    with that self reference. One finding per (function, parent), new when this change adds it."""
    from .owners import named, operation, place, row_function
    found = _findings()
    found.ran.add('delete')
    graph = change.graph
    models = graph._models()
    if not models.by_name:
        return found
    rows = [row for row in change.writes() if row.get('how') in ('prisma', 'sql') and row.get('model')]
    tests = {path for (path,) in graph.con.execute('SELECT path FROM file WHERE is_test = 1')}
    # A table no production code creates or updates rows in (only deletes or counts them) holds no rows the
    # code makes; its restricting relations are left out.
    created = {row['model'] for row in rows if row['file'] not in tests and not is_test_file(row['file'])
               and (row['kind'] in CREATING or row['kind'].startswith(('nested:create', 'nested:upsert', 'nested:update',
                                                                       'nested:connectOrCreate')))}
    queries = [row for row in graph.queries() if row.get('model')]
    by_function = {}
    for row in [*rows, *queries]:
        by_function.setdefault(row_function(row), []).append(row)
    groups = {}
    for row in rows:
        if row['kind'] not in DELETING[:4] or row.get('how') != 'prisma' or row['file'] in tests:
            continue
        groups.setdefault((row['file'], row['function'], row['model'], row_function(row)), []).append(row)
    # Rows production code creates or keeps with a self reference set (`parentDemandId: id`): a tree of that table.
    trees = {(row['model'], row['field']) for row in rows if row['file'] not in tests and not is_test_file(row['file'])
             and (row['kind'] in CREATING or row['kind'] == 'connect' or row['kind'].startswith(('nested:create', 'nested:upsert',
                                                                                                  'nested:connect')))
             and not (row.get('values') and not row.get('partial') and all(value is None for value in row['values']))}
    for (file, function, parent, ident), calls in sorted(groups.items()):
        # A self relation whose parent key can be null (a tree's parent: the root has none) is read only for a
        # delete of one row, outside a loop, of a table whose rows code links into a tree: a deleteMany or a
        # loop in hierarchy order removes children with their parents in ways this reading does not follow.
        one_row = any(row['kind'] in ('delete', 'nested:delete') and not row.get('loop') for row in calls)
        children = [child for child in graph.children(parent) if _restricts(child) and child['child'] in created
                    and not (child['child'] == parent and child['nullable']
                             and not (one_row and any((parent, key) in trees for key in child['keys'])))]
        if not children:
            continue
        tree = operation(graph, ident)
        own = {(row['file'], row['call_line']) for row in calls}      # a delete never handles its own children
        near = [item for node in tree for item in by_function.get(node, ())
                if (item['file'], item.get('call_line')) not in own]
        back = {field['name'] for description in models.by_name.get(parent, []) for field in description['fields']}
        open_children = {}
        for child in children:
            fields = {field['name'] for description in models.by_name.get(parent, []) for field in description['fields']
                      if field['type'] == child['child']}
            if not _handled(child, parent, [item for item in near if 'kind' in item], [item for item in near if 'counts' in item],
                            fields & back):
                open_children.setdefault(child['child'], []).append(child)
        if not open_children:
            continue
        by_name = 'name' in tree.values() or ident.startswith(('typescript/', 'javascript/', 'tsx/'))
        parts = []
        for name, relations in open_children.items():
            keys = [key for relation in relations for key in relation['keys']]
            parts.append(name + (f' ({len(keys)} foreign keys: {", ".join(keys)})' if len(keys) > 1 else ''))
        actions = '/'.join(dict.fromkeys(relation['on_delete'] or 'Restrict' for items in open_children.values() for relation in items))
        text = (f'Delete leaves child rows: {_places(calls)} {function} deletes {parent}; {actions} child tables {", ".join(parts)} '
                f'are not deleted, cleared or counted in the same operation' + (' (calls resolved by name)' if by_name else ''))
        step = 'delete or clear these child rows first, or count them and reject deletion; if database rejection is intentional, record the decision in .flowguard/ledger.toml:'
        entry = tuple(_structure_lines(f'delete:{file}:{function}:{parent}'))
        fresh = bool(change.baseline) and (file in change.files and _fresh_delete(change, file, function, parent)
                                          or bool(change.files & {child['file'] for items in open_children.values() for child in items}))
        member = named(ident)
        what = (f'deletes {parent}; {actions} child tables {", ".join(parts)} are not deleted, cleared or counted in the same operation'
                + (' (calls resolved by name)' if by_name else ''))
        found.issues.append(Issue(f'delete:{file}:{function}:{parent}', 4, f'delete {parent} ({function})', text, step,
                                  frozenset({member}), frozenset({file}), entry=entry,
                                  family='delete', subject=f'delete {parent}', parts=((member, place(calls[0]), what, step),),
                                  fresh=frozenset({member}) if fresh else frozenset(), detail=(f'delete at {_places(calls)}',)))
    return found


def _fresh_delete(change, file, function, parent):
    """Did the baseline version of this file lack a delete of `parent` in `function`?"""
    facts = change.old_facts(file)
    if not facts:
        return True
    old = [row for row in change.graph.writes(facts=[facts]) if row.get('model') == parent and row['function'] == function
           and row['kind'] in DELETING[:4]]
    return not old


def _structure_lines(name):
    from .ledger import structure_entry
    return structure_entry(name)


# ---- columns one description of a table lacks -----------------------------------------------------

def _schema_files(graph, *names):
    """The files of these descriptions: a file is itself, a Prisma schema folder (`prisma/schema/`, `./` at
    the root; `readers.prisma.schema_folders`) its Prisma files; a migrations folder has none."""
    import posixpath
    folders = {'' if name == './' else name[:-1] for name in names if name.endswith('/')}
    return frozenset({name for name in names if not name.endswith('/')}
                     | {row['file'] for row in graph.schemas() if row.get('kind') == 'prisma' and posixpath.dirname(row['file']) in folders})


def _short_path(path):
    """A description's last path part for the session brief: a file's name, a folder's name (`migrations`,
    `schema` of `prisma/schema/`); the repository root's schema folder stays `./`."""
    name = path.rstrip('/').rpartition('/')[2]
    return path if name in ('', '.') else name


def _gap_key(item):
    return item['table'].casefold(), item['description'], item['schema']


def columns(change):
    """Columns (and tables) one description has and another lacks (`MapHandle.schema_gaps()`): one issue per pair of
    descriptions with every table and column, new when this change adds a gap."""
    found = _findings()
    found.ran.add('columns')
    gaps = change.graph.schema_gaps()
    if not gaps:
        return found
    before = None
    changed = {item for item in change.files if item.endswith(('.prisma', '.sql'))}
    if change.baseline and changed:
        schemas = []
        for row in change.graph.schemas():
            if row['file'] in changed:
                facts = change.old_facts(row['file'])
                if facts.get('schema'):
                    schemas.append(dict(facts['schema'], file=row['file']))
            else:
                schemas.append(row)
        before = {(_gap_key(item), name) for item in change.graph.schema_gaps(schemas)
                  for name in [*item['missing'], *item['extra']]}
    pairs = {}
    for item in gaps:
        pairs.setdefault((item['description'], item['schema']), []).append(item)
    for (description, schema), items in sorted(pairs.items()):
        parts, fresh = [], False
        for item in items:
            if item['kind'].endswith('-table'):
                parts.append(f'missing table {item["table"]}')
            else:
                parts.append(f'{item["table"]}' + (f' ({item["file"]}:{item["line"]})' if item.get('file') else '')
                             + (f' missing {", ".join(item["missing"])}' if item['missing'] else '')
                             + (f'{"; " if item["missing"] else " "}extra {", ".join(item["extra"])}' if item.get('extra') else ''))
            fresh = fresh or before is not None and any((_gap_key(item), name) not in before
                                                         for name in [*item['missing'], *item['extra']])
        text = f'Columns missing between descriptions: {description} against {schema}: ' + '; '.join(parts)
        step = f'add the missing columns and tables; if this description is obsolete, mark it unused or remove it ({description})'
        found.issues.append(Issue(f'columns:{description}~{schema}', 3, f'missing columns {_short_path(description)}',
                                  text, step, frozenset(), _schema_files(change.graph, schema, description),
                                  family='columns', subject=f'columns {description} against {schema}',
                                  parts=(('', description, 'lacks ' + '; '.join(_ascii_part(part) for part in parts), step),),
                                  fresh=frozenset({''}) if fresh else frozenset()))
    return found


def _ascii_part(text):
    from .owners import _ascii
    return _ascii(text).strip()


def delete_rules(change):
    """Relations whose delete rule differs between two Prisma schemas of one database, a side without the
    foreign key included (`MapHandle.schema_delete_rules()`): code tested against one deletes rows the other
    refuses to delete, or nulls what the other keeps. One issue per pair, named by its two schemas (a file, or
    a schema folder `prisma/schema/`) in path order (whichever the pair is read against), listing every
    relation, new when this change adds a relation that differs."""
    found = _findings()
    found.ran.add('ondelete')
    rules = change.graph.schema_delete_rules()
    if not rules:
        return found

    def idents(item, relation):
        """One relation of one pair by its foreign key and by its name, whichever file the pair is read
        against: a relation is new only when neither was there with the same rules (a `@map` or `@@map`
        added to both schemas changes the key and keeps the name; a model renamed under its `@@map` keeps
        the key)."""
        name, rule, other, key = relation
        pair, rules = frozenset((item['schema'], item['description'])), frozenset({(item['schema'], rule), (item['description'], other)})
        return {(pair, 'key', key, rules), (pair, 'name', name, rules)}

    def listed(relations):
        return ', '.join(f'{name} ({NO_KEY if rule is None else rule} / {NO_KEY if other is None else other})'
                        for name, rule, other, _ in relations)

    before = None
    changed = {item for item in change.files if item.endswith('.prisma')}
    if change.baseline and changed:
        schemas = []
        for row in change.graph.schemas():
            facts = change.old_facts(row['file']) if row['file'] in changed else None
            if facts is None:
                schemas.append(row)
            elif facts.get('schema'):
                schemas.append(dict(facts['schema'], file=row['file']))
        before = set().union(*(idents(item, relation) for item in change.graph.schema_delete_rules(schemas)
                               for relation in item['relations']))
    for item in rules:
        schema, description, relations = item['schema'], item['description'], item['relations']
        head = f'onDelete differs: {description} against {schema}: '
        legend = f'parentheses show {schema}\'s rule first, then this description\'s rule'
        text = head + f'{len(relations)} relations ({legend}): ' + listed(relations)
        name = 'ondelete:' + '~'.join(sorted((schema, description)))
        step = ('align deletion rules in both schemas, including the test schema; if differences are intentional (for example, SQL Server disallows multiple cascade paths), '
                'record the decision in .flowguard/ledger.toml:')
        entry = tuple(_structure_lines(name))
        fresh = [relation for relation in relations if before is not None and before.isdisjoint(idents(item, relation))]
        what = (f'differs on {len(relations)} relations from {schema}'
                + (f', {len(fresh)} added in this change' if fresh else '') + ': ' + _ascii_part(listed(fresh or relations)))
        found.issues.append(Issue(name, 4, f'onDelete {_short_path(description)}', text, step, frozenset(),
                                  _schema_files(change.graph, schema, description), entry=entry,
                                  family='ondelete', subject=f'onDelete {description} against {schema}',
                                  parts=(('', description, what, step),), fresh=frozenset({''}) if fresh else frozenset(),
                                  detail=(f'parentheses show the rule of {schema} first, then that of {description}',)))
    return found


# ---- same-name functions whose bodies differ ------------------------------------------------------

def _module_functions(change, *, before=False):
    """The module-level production functions `copies` compares, in path and line order: (id, file, qual,
    fp, line, shape). `before` reads each file this change edits from its baseline bytes, as the code stood
    when the owner decided on its problems; a file the change adds has none then, and one it deletes is
    left out (its functions are no one's copy any more)."""
    rows = [row for row in change.graph.con.execute(
        "SELECT n.id, n.file, n.qual, n.fp, n.line, n.shape FROM node n JOIN file f ON f.path = n.file "
        "WHERE n.kind = 'function' AND f.is_test = 0 AND n.qual NOT LIKE '%.%' AND n.qual NOT LIKE '<%'")
        if not (before and row[1] in change.files)]
    if before:
        edited = sorted(file for (file,) in change.graph.con.execute('SELECT path FROM file WHERE is_test = 0')
                        if file in change.files)
        rows += [(f'{change._modules[file]}:{node["qual"]}', file, node['qual'], node['fp'], node['line'], node['shape'])
                 for file in edited for node in change.old_part(file, 'nodes') or ()
                 if node['kind'] == 'function' and '.' not in node['qual'] and not node['qual'].startswith('<')]
    return sorted(rows, key=lambda row: (row[1], row[4], row[0]))


def copies(change, index, *, before=False):
    """Module-level functions with one name in different files, almost the same structure (3-gram shape
    similarity SIMILAR_COPY or more) but different bodies: copies that drifted apart. One issue per set of
    files (two files that share several such functions are one issue), its members compared with the one
    in the first file by path. Issues only: a change gets the leads of `owners.changed_once`. A registered
    sensor is not listed. `before`: the problems as they stood at the change's baseline (`_module_functions`)."""
    from flowguard.structure.store import shape_list
    from .owners import STRUCTURAL_COPIES
    found = _findings()
    found.ran.add(STRUCTURAL_COPIES)          # the `copies` family also needs copy discovery (`owners.families_ran`)
    registered = {anchor.target for anchor in index.entries if anchor.kind == 'sensor'}
    groups = {}
    for ident, file, qual, fp, line, blob in _module_functions(change, before=before):
        if ident in registered or is_test_file(file):
            continue
        shape = set(shape_list(blob) if isinstance(blob, bytes) else blob or ())
        if len(shape) >= 8:
            groups.setdefault(qual, []).append((ident, file, fp, line, shape))
    by_files = {}
    for name, rows in sorted(groups.items()):
        first = rows[0]
        members = [first, *(row for row in rows[1:] if row[1] != first[1] and row[2] != first[2]
                            and len(row[4] & first[4]) / len(row[4] | first[4]) >= SIMILAR_COPY)]
        if len(members) > 1:
            by_files.setdefault(frozenset(row[1] for row in members), []).append((name, members))
    then = None
    if not before and by_files and change.baseline and change.baseline_paths():
        # The problems at the baseline, read once per change (`static_findings` asks for them too); a change that
        # alters no file has the baseline's code, so none of its members is new (`then` stays None).
        then = {issue.name: issue.nodes for issue in change.held('copies before', lambda: copies(change, index, before=True)).issues}
    for files, items in sorted(by_files.items(), key=lambda item: sorted(item[0])):
        names = [name for name, _ in items]
        text = (f'Same-named functions have different bodies (structural similarity at least {SIMILAR_COPY:g}): '
                + '; '.join(f'{name} ' + '  '.join(f'{file}:{line}' for _, file, _, line, _ in members) for name, members in items))
        label = names[0].strip('_').upper()
        step = (f'keep one implementation and call it elsewhere; to bind agreement, write same {label} ref above the reference and same {label} above each copy'
                f' (# or // flowguard:); rename intentionally different functions')
        name = 'copies:' + '+'.join(names)
        nodes = frozenset(row[0] for _, members in items for row in members)
        parts = tuple((ident, f'{file}:{qual}', f'has another body than the same-named {qual} in '
                       + ', '.join(sorted({other for _, other, *_ in members if other != file})), step)
                      for qual, members in items for ident, file, *_ in members)
        found.issues.append(Issue(name, 5, f'copy {names[0]}' + (f' ({len(names)} total)' if len(names) > 1 else ''),
                                  text, step, nodes, files, family='copies',
                                  subject='copies ' + '+'.join(names[:3]) + (f' (+{len(names) - 3} more)' if len(names) > 3 else ''), parts=parts,
                                  fresh=nodes - then.get(name, frozenset()) if then is not None else frozenset()))
    return found


# ---- fields several files write without an owner -------------------------------------------------

def written_field(row, tests):
    """The `Holder.field` a production write row writes, as the writers check counts it; None for a row it leaves
    out: a test's, a bookkeeping column, a class-body default, a module's own code, a patch of a module's class, a
    write whose field is not visible. `tests` are the map's test files."""
    holder, name = row.get('model') or row.get('table'), row.get('field') or row.get('db_column')
    if row.get('language', 'python') == 'python' and row['how'] == 'attribute' and '.' in str(holder):
        return None             # `module.Class.method = ...` patches a module's class; it writes no data field
    if not holder or row.get('unclear') or name in ('*', '?', None) or row['file'] in tests \
            or is_test_file(row['file']) or str(name).casefold() in BOOKKEEPING or row['function'] == '<module>' \
            or row['function'].rpartition('.')[2] == holder:      # a class-body default declares, it does not write
        return None
    return f'{holder}.{name}'


def _test_files(graph):
    return {path for (path,) in graph.con.execute('SELECT path FROM file WHERE is_test = 1')}


def writers(change, index, rows=None):
    """A model field written from WRITER_FILES or more production files with no data owner: an issue for
    the owner to decide (`check --all`, `show`); bookkeeping columns are left out. `rows` limits the
    writes read (show of one field). A member (a function writing it) is new when the baseline code had no such
    issue or that function did not write it then."""
    from .owners import place, row_function
    found = _findings()
    found.ran.add('writers')
    owned = {anchor.name.casefold() for anchor in index.entries if anchor.kind == 'owner'}
    tests = _test_files(change.graph)

    def unowned(rows):
        by_field = {}
        for row in rows:
            if (key := written_field(row, tests)) is not None:
                by_field.setdefault(key, []).append(row)
        return {name: rows for name, rows in by_field.items()
                if len({row['file'] for row in rows}) >= WRITER_FILES and name.casefold() not in owned}

    by_field = unowned(change.writes() if rows is None else rows)
    then = {name: {row_function(row) for row in rows}
            for name, rows in unowned(change.baseline_writes() if change.baseline_paths() else change.writes()).items()} \
        if by_field and rows is None and change.baseline else None
    for name, rows in sorted(by_field.items(), key=lambda item: (-len({row['file'] for row in item[1]}), item[0])):
        files = {row['file'] for row in rows}
        functions = list(dict.fromkeys(f'{row["file"]}:{row["function"]}' for row in rows))
        text = f'{name} is written by {len(files)} files without a registered writer agreement: ' + _places(rows)
        comment = '//' if any(row.get('language', 'python') != 'python' for row in rows) else '#'
        step = (f'ask the owner who is responsible; then write {comment} flowguard: writers {name} {",".join(functions)}'
                f' (retain only writers the owner approves), and record the decision in .flowguard/ledger.toml:')
        members = {}
        for row in rows:
            members.setdefault(row_function(row), row)
        what = f'writes {name}, which {len(files)} files write without a writers agreement'
        found.issues.append(Issue(f'writers:{name}', 6, f'write {name}', text, step,
                                  frozenset(row_function(row) for row in rows), frozenset(files),
                                  entry=tuple(_structure_lines(f'writers:{name}')), family='writers',
                                  subject=f'no writers agreement for {name}',
                                  parts=tuple((function, place(row), what, 'ask the owner who may write it')
                                              for function, row in sorted(members.items())),
                                  fresh=frozenset(set(members) - then.get(name, set())) if then is not None else frozenset()))
    return found


# ---- fields written together with one field: with= candidates for show --------------------------

PARTNER_SHARE = 0.5          # share of a field's writing functions that also write a field before it is a with= candidate
PARTNERS_SHOWN = 5


def co_written(change, name):
    """Lines for `show Model.field`: other fields most of its production writers also write in the same
    function, each with the writers that leave it out and the `owner ... with=` line to copy. Reference
    only: writing two fields together often is no rule until the owner says so."""
    from .owners import row_function
    tests = {path for (path,) in change.graph.con.execute('SELECT path FROM file WHERE is_test = 1')}
    def field_of(row):
        holder, column = row.get('model') or row.get('table'), row.get('field') or row.get('db_column')
        bound = not row.get('unclear') and not (row.get('how') == 'name' and row.get('language', 'python') != 'python')
        if not bound or not holder or column in ('*', '?', None) or row['file'] in tests or is_test_file(row['file']) \
                or row['function'] == '<module>':
            return None
        return f'{holder}.{column}'
    by_function, places = {}, {}
    for row in change.writes():
        key = field_of(row)
        if key is not None:
            by_function.setdefault(row_function(row), set()).add(key)
            if key.casefold() == name.casefold():
                places.setdefault(row_function(row), f'{row["file"]}:{row["line"]} {row["function"]}')
    writers = sorted(places)
    if len(writers) < 2:
        return []
    shared = Counter(other for function in writers for other in by_function[function]
                     if other.casefold() != name.casefold() and other.rpartition('.')[2].casefold() not in BOOKKEEPING)
    target = next(key for function in writers for key in by_function[function] if key.casefold() == name.casefold())
    comment = '//' if any(ident.startswith(('typescript/', 'tsx/', 'javascript/')) for ident in writers) else '#'
    lines = []
    for other, count in sorted(shared.items(), key=lambda item: (-item[1], item[0]))[:PARTNERS_SHOWN]:
        if count < 2 or count < PARTNER_SHARE * len(writers):
            break
        alone = [places[function] for function in writers if other not in by_function[function]]
        lines.append(f'with= candidate (reference only): {other} is written by {count} of the {len(writers)} functions '
                     f'that write {target}' + (f'; not by {"  ".join(alone)}' if alone else '')
                     + f' -> if the owner says they change together: {comment} flowguard: together {target} {other}')
    return lines


# ---- tables code reads or deletes but never makes rows in -----------------------------------------

def _uses(graph, models, writes, queries):
    """{model: {verb: rows}} of the models production code reads, deletes or updates and never makes rows in, with
    these schema models, write rows and query rows (`uncreated`)."""
    views = {name for name, items in models.by_name.items() if all(item['kind'] == 'view' for item in items)}
    tests = _test_files(graph)
    def live(row):
        return row['file'] not in tests and not is_test_file(row['file']) and not graph.archived(row['file'])
    rows = [row for row in writes if row.get('how') in ('prisma', 'sql') and row.get('model') and live(row)]
    made = {row['model'] for row in rows if row['kind'] in INSERTING
            or row['kind'].startswith(('nested:create', 'nested:upsert', 'nested:connectOrCreate'))}
    uses = {}
    for row in [*rows, *(row for row in queries if row.get('model') and live(row))]:
        if row['model'] in made or row['model'] in views:
            continue
        verb = 'delete' if 'kind' in row and row['kind'] in DELETING else 'update' if 'kind' in row else 'read'
        uses.setdefault(row['model'], {}).setdefault(verb, []).append(row)
    return {model: verbs for model, verbs in uses.items() if set(verbs) != {'update'}}  # only updated: see writers


def _baseline_queries(change, models):
    """The Prisma reads of the baseline code, bound to the baseline's models by accessor as `MapHandle.queries`
    binds them: the map's for the files this change leaves alone, the baseline bytes' for the others."""
    paths = change.baseline_paths()
    facts = [data for path, _, data in change.graph._kinds('language', 'queries') if path not in paths]
    facts += [record for record in map(change.old_facts, sorted(paths)) if record]
    return [dict(row, model=models.by_accessor.get(row['accessor']), language=data.get('language'))
            for data in facts for row in data.get('queries', ())]


def uncreated(change):
    """A Prisma model production code reads or deletes (also updates) while no production code or live SQL
    makes its rows (create, createMany, upsert, a nested create, INSERT): the rows come from elsewhere or the
    reads are dead. A Prisma `view` has no rows to make. One issue per model. A member (a function that uses the
    model) is new when the baseline code did not use it so, or made its rows."""
    from .owners import place, row_function
    found = _findings()
    found.ran.add('uncreated')
    graph = change.graph
    if not graph._models().by_name:
        return found
    uses = _uses(graph, graph._models(), change.writes(), graph.queries())
    then = None
    if uses and change.baseline and not change.baseline_paths():
        then = {model: {row_function(row) for items in verbs.values() for row in items} for model, verbs in uses.items()}
    elif uses and change.baseline:
        models = change.baseline_definitions().models
        then = {model: {row_function(row) for items in verbs.values() for row in items}
                for model, verbs in _uses(graph, models, change.baseline_writes(), _baseline_queries(change, models)).items()}
    for model, verbs in sorted(uses.items()):
        text = (f'Table whose rows are never created by this code: {model} ' + ', '.join(f'{verb} {_places(verbs[verb])}' for verb in ('read', 'delete', 'update') if verb in verbs)
                + '; no create/upsert/INSERT exists')
        step = 'ask the owner where these rows come from (seeds, migrations or external systems); if there is no source, remove these reads and deletes; if intentional, record the decision in .flowguard/ledger.toml:'
        members = {}
        for verb in ('read', 'delete', 'update'):
            for row in verbs.get(verb, ()):
                members.setdefault(row_function(row), (row, []))[1].append(verb)
        parts = tuple((function, place(row), ' and '.join(verb + 's' for verb in dict.fromkeys(done)) + f' {model}, whose rows no code creates',
                       'ask the owner where these rows come from') for function, (row, done) in sorted(members.items()))
        found.issues.append(Issue(f'uncreated:{model}', 7, f'row creation {model}', text, step,
                                  frozenset(row_function(row) for items in verbs.values() for row in items),
                                  frozenset(row['file'] for items in verbs.values() for row in items),
                                  entry=tuple(_structure_lines(f'uncreated:{model}')), family='uncreated',
                                  subject=f'uncreated {model}', parts=parts,
                                  fresh=frozenset(set(members) - then.get(model, set())) if then is not None else frozenset()))
    return found


# ---- label tables that disagree --------------------------------------------------------------------

def labels(change):
    """Label tables that disagree (`MapHandle.label_tables()`): copies of one table of labels that spell a
    key's label differently, and lookup tables that lack a key their copies have. One issue per family, new when this
    change edits or adds one of its tables."""
    found = _findings()
    found.ran.add('labels')
    for family in change.graph.label_tables():
        tables = family['tables']
        names = [table['name'] for table in tables]
        def ref(i):
            return names[i] if names.count(names[i]) == 1 else f'{names[i]} ({tables[i]["file"].rpartition("/")[2]}:{tables[i]["line"]})'
        parts = [f'{key} ' + ' versus '.join(f'{label!r} ({", ".join(ref(i) for i in where)})' for label, where in spelled.items())
                 for key, spelled in family['differ'].items()]
        parts += [f'{ref(i)} lacks {", ".join(keys)}' for i, keys in family['lacking'].items()]
        text = ('Label tables disagree: ' + ', '.join(f'{table["file"]}:{table["line"]} {table["name"]}' for table in tables)
                + ': ' + '; '.join(parts))
        head = tables[0]
        name = f'labels:{head["file"]}:{head["name"]}'
        step = ('derive these tables from one source, or align labels and add missing keys; if differences are intentional (abbreviations or another purpose), record the decision in '
                '.flowguard/ledger.toml:')
        fresh = bool(change.baseline) and any(_table_changed(change, table) for table in tables)
        found.issues.append(Issue(name, 8, f'labels {head["name"]}', text, step, frozenset(),
                                  frozenset(table['file'] for table in tables),
                                  entry=tuple(_structure_lines(name)), family='labels', subject=f'labels {head["name"]}',
                                  parts=(('', f'{head["file"]}:{head["name"]}', 'disagrees with '
                                          + ', '.join(f'{table["file"]}:{table["name"]}' for table in tables[1:]) + ': '
                                          + _ascii_part('; '.join(parts)), 'derive these tables from one source'),),
                                  fresh=frozenset({''}) if fresh else frozenset()))
    return found


def _table_changed(change, table):
    """Whether this change adds the table or changes its keys or labels."""
    if table['file'] not in change.files:
        return False
    old = [row for row in change.old_facts(table['file']).get(table['kind'], ()) if row['name'] == table['name']]
    return not old or {key: value for key, value in old[0]['values'].items() if key} != table['values']


# ---- decisions, touched issues, the --all section and the brief ----------------------------------

def decided(cfg, index, issues, decisions=None):
    """(open issues, input findings): issues the `[structure]` section decides are closed; a decision on who writes a
    field without its owner anchor is an input finding, red, with the anchor line to copy. The section itself is a
    5.0-deprecated feature: reading it prints the deprecated line (`ledger.structure_decisions`); `decisions` are the
    decisions a change already read (`owners.Change.decisions`)."""
    from .ledger import LEDGER, STRUCTURE, structure_decisions
    if decisions is None:
        decisions = structure_decisions(cfg)[0]    # malformed decisions are the ledger's red lines
    owned = {anchor.name.casefold() for anchor in index.entries if anchor.kind == 'owner'}
    wrong = []
    for name in sorted(decisions):
        kind, _, target = name.partition(':')
        if kind == 'writers' and target.casefold() not in owned:
            issue = next((item for item in issues if item.name == name), None)
            anchor = issue.step.partition('then write ')[2].partition(' (retain only')[0] if issue else \
                f'# flowguard: writers {target} <function,...> (use // for JS/TS)'
            wrong.append(Issue(f'structure-decision:{name}', LINES_ONLY, f'decision {name}',
                               f'Structure decision [structure."{name}"] records responsibility but has no writers agreement '
                               f'-> add beside the responsible function: {anchor}', f'add {anchor}',
                               files=frozenset({LEDGER}), family='input', subject=f'ledger [{STRUCTURE}."{name}"]',
                               parts=(('', f'{LEDGER}:[{STRUCTURE}."{name}"]', 'records who writes the field, but no writers agreement exists',
                                       f'add beside the responsible function: {anchor}'),), fresh=frozenset({''})))
    return [issue for issue in issues if issue.name not in decisions], wrong


def _order(issues):
    """By severity; fields without an owner by how many files write them, the most first."""
    return sorted(issues, key=lambda issue: (issue.rank, -len(issue.files) if issue.rank == 6 else 0, issue.name))


def summary(issues):
    """The count and the three heaviest short names, which the session brief shows; fields without an
    owner are counted apart (they wait for the owner, not for a fix)."""
    ordered = _order([issue for issue in issues if issue.rank != LINES_ONLY])
    problems = [issue for issue in ordered if issue.rank != 6]
    return dict(count=len(problems), writers=len(ordered) - len(problems), top=[issue.short for issue in ordered[:3]])


def brief_line(cfg):
    """The brief's line from the last check (`cache.structure_summary`), or '' when none recorded one."""
    from . import cache
    data = cache.structure_summary(cfg)
    if not data or not data['count'] and not data['writers']:
        return ''
    return (f'{data["count"]} open structure issues' + (f' ({data["writers"]} other fields have multiple writers and no writer agreement)' if data['writers'] else '')
            + '; highest severity: ' + '; '.join(data['top']) + ' (last check; check --static --all lists every issue and next step)')


def assess(cfg, change, index, found):
    """Close the issues the owner decided and add the decision findings to `found`; `found.summary` is for the
    session brief. For the 4.3 lines a decided issue leaves `found.issues` (its name goes to `found.decided`, counted
    as an ignore entry is) only when its family may be ignored: a decision never closes a finding that can be red."""
    from .signals import FAMILIES
    issues, wrong = decided(cfg, index, found.issues, change.decisions())
    still = {issue.name for issue in issues}
    closed = [issue for issue in found.issues if issue.name not in still and issue.family in FAMILIES and FAMILIES[issue.family][2]]
    found.decided.extend(dict.fromkeys(issue.name for issue in closed))
    gone = {id(issue) for issue in closed}
    found.issues = [issue for issue in found.issues if id(issue) not in gone] + wrong
    found.summary = summary(issues)
    return found
