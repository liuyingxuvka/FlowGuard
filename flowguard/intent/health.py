"""Structure health: the map checks that need no test run, and the open structure problems they leave.

Each check reads the one map (`MapHandle.writes()`, `value_sets()`, `queries()`, `children()`,
`schema_gaps()`, `call_tree()`) and reports only what this change adds: red for a value outside its
declared set, leads for a delete that leaves restricting children, a column one description of a table
lacks and two same-name functions whose bodies differ. Every problem, old ones too, is also an `Issue`
with a stable name; `check --all` and `check --static --all` list them by severity, and a change that
touches an open one gets a single lead. The owner's decision in the `[structure]` section of
`.flowguard/ledger.toml` (eight words or more, sourced from stored owner words or a written rule)
closes an issue; a decision on who writes a field also needs its `owner ... writers=` anchor.
Fields that several files write without an owner are issues only (`--all`, `show`).
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from flowguard.map.common import is_test_file

RANKS = {1: '取值', 2: '配对', 3: '缺列', 4: '删除', 5: '副本', 6: '写入'}
BOOKKEEPING = {'id', 'createdat', 'updatedat', 'created_at', 'updated_at', 'createdbyid', 'updatedbyid',
               'created_by', 'updated_by', 'revision', 'version'}     # written by every writer on purpose
WRITER_FILES = 3             # files writing one field without an owner before it is an issue
SIMILAR_COPY = 0.8           # shape similarity of two same-name functions that makes them copies
CREATING = ('create', 'createMany', 'createManyAndReturn', 'upsert:create', 'upsert:update', 'update', 'updateMany',
            'updateManyAndReturn', 'sql:insert', 'sql:update')   # code that makes or keeps rows of a table
SHOWN_GROUPS = 3             # copies or unowned fields the --all listing shows one by one; more become one line
DELETING = ('delete', 'deleteMany', 'nested:delete', 'nested:deleteMany', 'sql:delete')
RESTRICTING = ('NoAction', 'Restrict')


@dataclass(frozen=True)
class Issue:
    """One open structure problem: a stable name, its severity rank, a short name for the session brief,
    the problem with every place, the next step to copy, and the functions and files that touch it."""
    name: str
    rank: int
    short: str
    text: str
    step: str
    nodes: frozenset = frozenset()
    files: frozenset = frozenset()
    new: bool = False            # this change added it: it is already a red line or a lead
    entry: tuple = ()            # lines to copy (a ledger entry), shown indented under the step

    def next_step(self):
        return '\n'.join([self.step, *('    ' + line for line in self.entry)])


def _findings():
    from .owners import Findings
    return Findings()


def _places(rows):
    return '  '.join(dict.fromkeys(f'{row["file"]}:{row["line"]}' for row in rows))


# ---- values outside a declared set (Prisma enums, SQL CHECK, JS/TS annotated members) --------------

def _foreign_writes(change, facts=None):
    """Write rows outside Python with a readable value, keyed for the gate by `Model.field`."""
    graph = change.graph
    rows = graph.writes(facts=facts) if facts is not None else change.writes()
    out = [dict(row, field=f'{row["model"]}.{row["field"]}', values=[v for v in row.get('values', ()) if v is not None])
           for row in rows if row.get('model') and not row.get('unclear') and row.get('language', 'python') != 'python'
           and row.get('values')]
    out += [dict(row, field=f'{row["container"]}.{row["field"]}', gate=f'ts:{row["container"]}.{row["field"]}',
                 values=[v for v in row.get('values', ()) if v is not None])     # gated by the TS type's own sets
            for row in graph.typed_writes(facts=facts) if row.get('values')]
    return [row for row in out if row['values']]


def values(change, *, everything=False):
    """A value written outside its declared set is red when this change adds the write or changes the
    declaration; every one is an issue. One gate decides (`anchors.outside_sets`)."""
    from .anchors import declared_sets, outside_sets
    from .owners import row_function
    found = _findings()
    sets = change.graph.value_sets()
    if not sets:
        return found
    table = declared_sets((), foreign=sets)
    outside = list(outside_sets(table, _foreign_writes(change)))
    if not outside:
        return found
    key = lambda row, declared, value: (row['file'], row_function(row), row['field'], declared['where'], repr(value))
    before = Counter()
    for file in {row['file'] for row, _, _ in outside} & change.files:
        facts = change.old_facts(file)
        if facts:
            before.update(key(row, declared, value) for row, declared, value
                          in outside_sets(table, _foreign_writes(change, [facts])))
    now = Counter(key(row, declared, value) for row, declared, value in outside)
    by_field, names = {}, set()
    for row, declared, value in outside:
        by_field.setdefault((row.get('gate', row['field']), declared['where']), (declared, []))[1].append((row, value))
    for (_, where), (declared, items) in sorted(by_field.items()):
        name = declared['name']
        # a field's second set (a CHECK beside its enum, a TS type of a model's name) is its own issue
        issue_name = f'values:{name}' if f'values:{name}' not in names else f'values:{name}:{where}'
        names.add(issue_name)
        changed_set = declared.get('file') in change.files
        fresh = [(row, value) for row, value in items if changed_set or row['file'] in change.files
                 and now[key(row, declared, value)] > before[key(row, declared, value)]]
        allowed = '|'.join(map(str, declared['values']))
        def line(chosen):
            return ('取值不在声明集合里：' + '  '.join(f'{row["file"]}:{row["line"]} {name}={value!r}' for row, value in chosen)
                    + f'，允许 {allowed}（{where}）')
        step = '改用集合里的值；集合真要加值，先改那条声明（' + where + '）'
        if fresh and change.baseline:
            found.red.append(line(fresh) + ' → ' + step)
        found.issues.append(Issue(issue_name, 1, f'取值 {name}', line(items), step,
                                  frozenset(row_function(row) for row, _ in items), frozenset(row['file'] for row, _ in items),
                                  new=bool(fresh and change.baseline)))
    return found


# ---- deletes that leave restricting children (Prisma) --------------------------------------------

def _restricts(child):
    """NoAction/Restrict, or no onDelete on a required relation (Prisma's default Restrict; an optional
    relation defaults to SetNull and does not block the delete)."""
    return child['on_delete'] in RESTRICTING or not child['on_delete'] and child['required']


def _handled(child, parent, rows, queries, back):
    """Does one of these writes or reads delete, null or count the child's rows of this parent?"""
    keys = set(child['keys']) | {child['relation']}
    for row in rows:
        if row.get('model') == child['child'] and (row['kind'] in DELETING or row['field'] in child['keys']
                                                   and None in (row.get('values') or ()) or row['kind'] == 'disconnect'):
            return True
    for row in queries:
        if row.get('model') == child['child'] and set(row['keys']) & keys:
            return True
        if row.get('model') == parent and ('*' in row['counts'] or set(row['counts']) & back or set(row['loads']) & back):
            return True
    return False


def deletes(change, *, everything=False):
    """A Prisma delete of a parent whose restricting children (NoAction/Restrict) are not deleted, nulled
    or counted anywhere in the same operation: the function's callers three levels up and what they call
    three levels down (JS/TS calls resolved by name). Tables the code never creates rows in are left out.
    One lead per (function, parent); a lead only when this change adds it."""
    from .owners import named, operation, row_function
    found = _findings()
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
    for (file, function, parent, ident), calls in sorted(groups.items()):
        # An optional self relation (a tree's parent) is left out: deletes of a tree remove children with or before
        # their parents in ways this reading does not follow (loops in hierarchy order, one deleteMany).
        children = [child for child in graph.children(parent) if _restricts(child) and child['child'] in created
                    and not (child['child'] == parent and not child['required'])]
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
            parts.append(name + (f'（{len(keys)} 个外键：{"、".join(keys)}）' if len(keys) > 1 else ''))
        actions = '/'.join(dict.fromkeys(relation['on_delete'] or 'Restrict' for items in open_children.values() for relation in items))
        text = (f'删除没处理子表：{_places(calls)} {function} 删 {parent}，{actions} 子表 {"、".join(parts)} '
                f'在同一操作里没删、没置空、没计数' + ('（调用按名字解析）' if by_name else ''))
        step = '删除前先删或置空这些子表的行，或先计数并拒绝删除；有意交给数据库拒绝，就把决定记进 .flowguard/ledger.toml：'
        entry = tuple(_structure_lines(f'delete:{file}:{function}:{parent}'))
        fresh = bool(change.baseline) and (file in change.files and _fresh_delete(change, file, function, parent)
                                          or bool(change.files & {child['file'] for items in open_children.values() for child in items}))
        issue = Issue(f'delete:{file}:{function}:{parent}', 4, f'删除 {parent}（{function}）', text, step,
                      frozenset({named(ident)}), frozenset({file}), new=fresh, entry=entry)
        if fresh:
            found.leads.append(text + ' → ' + issue.next_step())
        found.issues.append(issue)
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

def _gap_key(item):
    return item['table'].casefold(), item['description'], item['schema']


def columns(change, *, everything=False):
    """Columns (and tables) one description has and another lacks (`MapHandle.schema_gaps()`), one line per
    pair of descriptions with every table and column: a lead when this change adds a gap; each pair is an issue."""
    found = _findings()
    gaps = change.graph.schema_gaps()
    if not gaps:
        return found
    before = None
    changed = {item for item in change.files if item.endswith(('.prisma', '.sql'))}
    if change.baseline and changed:
        from flowguard.structure.readers.prisma import gaps as compare
        schemas = []
        for row in change.graph.schemas():
            if row['file'] in changed:
                facts = change.old_facts(row['file'])
                if facts.get('schema'):
                    schemas.append(dict(facts['schema'], file=row['file']))
            else:
                schemas.append(row)
        before = {(_gap_key(item), name) for item in compare(schemas) for name in [*item['missing'], *item['extra']]}
    pairs = {}
    for item in gaps:
        pairs.setdefault((item['description'], item['schema']), []).append(item)
    for (description, schema), items in sorted(pairs.items()):
        parts, fresh = [], False
        for item in items:
            if item['kind'].endswith('-table'):
                parts.append(f'没有表 {item["table"]}')
            else:
                parts.append(f'{item["table"]}' + (f'（{item["file"]}:{item["line"]}）' if item.get('file') else '')
                             + (f' 缺 {"、".join(item["missing"])}' if item['missing'] else '')
                             + (f'{"，" if item["missing"] else " "}多出 {"、".join(item["extra"])}' if item.get('extra') else ''))
            fresh = fresh or before is not None and any((_gap_key(item), name) not in before
                                                         for name in [*item['missing'], *item['extra']])
        text = f'几份描述之间缺的列：{description} 对照 {schema}：' + '；'.join(parts)
        step = f'补上缺的列和表；那份描述过时了，就写明它不再使用或删掉它（{description}）'
        if fresh:
            found.leads.append(text + ' → ' + step)
        found.issues.append(Issue(f'columns:{description}~{schema}', 3, f'缺列 {description.rstrip("/").rpartition("/")[2]}',
                                  text, step, frozenset(), frozenset({schema, description.rstrip('/')}), new=fresh))
    return found


# ---- same-name functions whose bodies differ ------------------------------------------------------

def copies(change, index):
    """Module-level functions with one name in different files, almost the same structure (3-gram shape
    similarity SIMILAR_COPY or more) but different bodies: copies that drifted apart. One issue per set of
    files (two files that share several such functions are one issue). Issues only: a change gets the
    leads of `owners.changed_once`. A registered sensor is not listed."""
    from flowguard.structure.store import shape_list
    found = _findings()
    registered = {anchor.target for anchor in index.entries if anchor.kind == 'sensor'}
    groups = {}
    for ident, file, qual, fp, line, blob in change.graph.con.execute(
            "SELECT n.id, n.file, n.qual, n.fp, n.line, n.shape FROM node n JOIN file f ON f.path = n.file "
            "WHERE n.kind = 'function' AND f.is_test = 0 AND n.qual NOT LIKE '%.%' AND n.qual NOT LIKE '<%'"):
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
    for files, items in sorted(by_files.items(), key=lambda item: sorted(item[0])):
        names = [name for name, _ in items]
        text = (f'同名函数、函数体不同（结构相似度不低于 {SIMILAR_COPY:g}）：'
                + '；'.join(f'{name} ' + '  '.join(f'{file}:{line}' for _, file, _, line, _ in members) for name, members in items))
        label = names[0].strip('_').upper()
        step = (f'留一份、别处改成调用它；要锁定：负责人上方写 owner {label}、副本上方写 sensor {label}'
                f'（# 或 // flowguard:）；有意不同就改名')
        found.issues.append(Issue('copies:' + '+'.join(names), 5, f'副本 {names[0]}' + (f' 等 {len(names)} 个' if len(names) > 1 else ''),
                                  text, step, frozenset(row[0] for _, members in items for row in members), files))
    return found


# ---- fields several files write without an owner -------------------------------------------------

def writers(change, index, rows=None):
    """A model field written from WRITER_FILES or more production files with no data owner: an issue for
    the owner to decide (`check --all`, `show`); bookkeeping columns are left out. `rows` limits the
    writes read (show of one field)."""
    from .owners import row_function
    found = _findings()
    owned = {anchor.name.casefold() for anchor in index.entries if anchor.kind == 'owner'}
    tests = {path for (path,) in change.graph.con.execute('SELECT path FROM file WHERE is_test = 1')}
    by_field = {}
    for row in change.writes() if rows is None else rows:
        holder, name = row.get('model') or row.get('table'), row.get('field') or row.get('db_column')
        if row.get('language', 'python') == 'python' and row['how'] == 'attribute' and '.' in str(holder):
            continue            # `module.Class.method = ...` patches a module's class; it writes no data field
        if not holder or row.get('unclear') or name in ('*', '?', None) or row['file'] in tests \
                or is_test_file(row['file']) or str(name).casefold() in BOOKKEEPING or row['function'] == '<module>' \
                or row['function'].rpartition('.')[2] == holder:      # a class-body default declares, it does not write
            continue
        by_field.setdefault(f'{holder}.{name}', []).append(row)
    for name, rows in sorted(by_field.items(), key=lambda item: (-len({row['file'] for row in item[1]}), item[0])):
        files = {row['file'] for row in rows}
        if len(files) < WRITER_FILES or name.casefold() in owned:
            continue
        functions = list(dict.fromkeys(row['function'] for row in rows))
        text = f'{name} 有 {len(files)} 个文件在写，没有登记负责人：' + _places(rows)
        comment = '//' if any(row.get('language', 'python') != 'python' for row in rows) else '#'
        step = (f'先告诉主人，问谁负责；定下来后在负责的函数旁写 {comment} flowguard: owner {name} writers={",".join(functions)}'
                f'（只留主人认可的写入者），并在 .flowguard/ledger.toml 记下决定：')
        found.issues.append(Issue(f'writers:{name}', 6, f'写入 {name}', text, step,
                                  frozenset(row_function(row) for row in rows), frozenset(files),
                                  entry=tuple(_structure_lines(f'writers:{name}'))))
    return found


# ---- decisions, touched issues, the --all section and the brief ----------------------------------

def decided(cfg, index, issues):
    """(open issues, red findings): issues the `[structure]` section decides are closed; a decision on who
    writes a field without its owner anchor is red, with the anchor line to copy."""
    from .ledger import structure_decisions
    decisions, _ = structure_decisions(cfg)        # malformed decisions are the ledger's red lines
    owned = {anchor.name.casefold() for anchor in index.entries if anchor.kind == 'owner'}
    red = []
    for name in sorted(decisions):
        kind, _, target = name.partition(':')
        if kind == 'writers' and target.casefold() not in owned:
            issue = next((item for item in issues if item.name == name), None)
            anchor = issue.step.partition('旁写 ')[2].partition('（只留')[0] if issue else \
                f'# flowguard: owner {target} writers=<函数,…>（JS/TS 用 //）'
            red.append(f'结构决定 [structure."{name}"] 记下了谁负责，但没有 owner 锚点 → 在负责的函数旁加一行：{anchor}')
    return [issue for issue in issues if issue.name not in decisions], red


def touched(change, issues):
    """One lead per open issue this change touches (a write, delete or copy it edits, or a schema file it
    changes), unless the change already reported it."""
    if not change.baseline or not change.files:
        return []
    edited = change.touched()
    out = []
    for issue in issues:
        if issue.new:
            continue
        hit = issue.nodes & edited or issue.rank == 3 and issue.files & change.files \
            or issue.rank == 1 and any(file in change.files for file in issue.files if file.endswith(('.prisma', '.sql')))
        if hit:
            out.append(f'未决结构问题：{issue.text} → {issue.next_step()}')
    return out


def _order(issues):
    """By severity; fields without an owner by how many files write them, the most first."""
    return sorted(issues, key=lambda issue: (issue.rank, -len(issue.files) if issue.rank == 6 else 0, issue.name))


def section(issues):
    """The `--all` listing: every open issue by severity, each with its next step, untruncated. Copies and
    fields without an owner wait for the owner's choice: more than SHOWN_GROUPS of either become one line
    (by name, the most copies or writer files first); `show NAME` lists any one of them in full."""
    ordered = _order(issues)
    if not ordered:
        return []
    lines = [f'结构问题 {len(ordered)} 项（按严重程度；主人定下后记进 .flowguard/ledger.toml 的 [structure] 就不再提示）：']
    number = 0
    for rank in sorted(RANKS):
        group = [issue for issue in ordered if issue.rank == rank]
        if rank in (5, 6) and len(group) > SHOWN_GROUPS:
            number += 1
            if rank == 5:
                group.sort(key=lambda issue: (-len(issue.nodes), issue.name))
                names = '、'.join(f'{issue.name.partition(":")[2]}（{len(issue.nodes)} 份）' for issue in group)
                lines.append(f'{number}. 副本：{len(group)} 组同名函数、函数体不同（结构相似度不低于 {SIMILAR_COPY:g}）：{names}')
                lines.append('   下一步：show 名字 列出每份的位置；每组留一份、别处调用它，或用 owner/sensor 锁定，有意不同就改名')
            else:
                models = {}
                for issue in group:
                    models.setdefault(issue.name.partition(':')[2].rpartition('.')[0], []).append(issue)
                parts = sorted(models.items(), key=lambda item: (-max(len(issue.files) for issue in item[1]), item[0]))
                names = '、'.join(f'{model}（{len(items)} 个字段，最多 {max(len(issue.files) for issue in items)} 个文件）'
                                 for model, items in parts)
                lines.append(f'{number}. 写入：{len(group)} 个字段由 {WRITER_FILES} 个以上文件写入、没有登记负责人：{names}')
                lines.append('   下一步：先告诉主人，问谁负责；show 模型.字段 列出写入点和可以照抄的 owner 行、[structure] 条目')
            continue
        for issue in group:
            number += 1
            lines.append(f'{number}. {RANKS[issue.rank]}：{issue.text}')
            lines.append(f'   下一步：{issue.step}')
            lines.extend('       ' + line for line in issue.entry)
    return lines


def summary(issues):
    """The count and the three heaviest short names, which the session brief shows; fields without an
    owner are counted apart (they wait for the owner, not for a fix)."""
    ordered = _order(issues)
    problems = [issue for issue in ordered if issue.rank != 6]
    return dict(count=len(problems), writers=len(ordered) - len(problems), top=[issue.short for issue in ordered[:3]])


def brief_line(cfg):
    """The brief's line from the last check (`cache.structure_summary`), or '' when none recorded one."""
    from . import cache
    data = cache.structure_summary(cfg)
    if not data or not data['count'] and not data['writers']:
        return ''
    return (f'未决结构问题 {data["count"]} 项' + (f'（另 {data["writers"]} 个字段多处写入、没有负责人）' if data['writers'] else '')
            + '，最重：' + '；'.join(data['top']) + '（上次检查；check --static --all 列出全部和下一步）')


def assess(cfg, change, index, found, *, everything=False):
    """Close decided issues and add the touched leads and decision reds to `found`; `found.summary` is for
    the session brief, `found.section` the `--all` listing."""
    issues, red = decided(cfg, index, found.issues)
    found.red.extend(red)
    found.leads.extend(touched(change, issues))
    found.summary = summary(issues)
    found.section = section(issues) if everything else []
    return found
