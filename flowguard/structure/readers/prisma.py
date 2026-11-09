"""Prisma schema facts and the binding of Prisma client write paths to models, fields and columns.

The schema reader is line based: `model`, `view`, `type` and `enum` blocks; field name, type,
`?`/`[]`, `@map("...")`, `@relation(name?, fields: [...], references: [...])`, and the block
attribute `@@map("...")`. Prisma is never run. A field whose type names a model of a mapped schema
is a relation (no column of its own); every other field is a column.

`bind` turns the syntax paths the TS/JS reader records for `<client>.<accessor>.<method>(...)`
into writes: the accessor names a model (`centralEmployee` -> `CentralEmployee`), a nested
operation follows the relation to its model, and `connect`/`connectOrCreate`/`disconnect`/`set`
write the foreign-key fields that `@relation(fields: [...])` names, on whichever side holds them.
"""
from __future__ import annotations

import hashlib
import re

BLOCK = re.compile(r'^\s*(model|view|type|enum)\s+([A-Za-z_]\w*)\s*\{\s*$')
FIELD = re.compile(r'^\s*([A-Za-z_]\w*)\s+([A-Za-z_]\w*(?:\([^)]*\))?)(\[\])?(\?)?(?:\s+(.*))?$')
MAP = re.compile(r'@map\(\s*(?:name\s*:\s*)?"([^"]*)"')
BLOCK_MAP = re.compile(r'@@map\(\s*(?:name\s*:\s*)?"([^"]*)"')
ON_DELETE = re.compile(r'@relation\(.*\bonDelete\s*:\s*(\w+)')
SCALARS = {'String', 'Boolean', 'Int', 'BigInt', 'Float', 'Decimal', 'DateTime', 'Json', 'Bytes'}
CONNECTING = {'connect', 'connectOrCreate', 'disconnect', 'set'}


def _strip_comment(line: str) -> str:
    out, quote = [], False
    for i, ch in enumerate(line):
        if ch == '"' and (i == 0 or line[i - 1] != '\\'):
            quote = not quote
        if not quote and line[i:i + 2] == '//':
            break
        out.append(ch)
    return ''.join(out).rstrip()


def _list(text: str, key: str) -> list[str]:
    found = re.search(key + r'\s*:\s*\[([^\]]*)\]', text)
    return [item.strip() for item in found.group(1).split(',') if item.strip()] if found else []


def relation(attributes: str):
    """name, fields and references of an `@relation(...)` attribute, or None."""
    found = re.search(r'@relation\((.*)\)', attributes)
    if not found and '@relation' not in attributes:
        return None
    body = found.group(1) if found else ''
    name = re.match(r'\s*(?:name\s*:\s*)?"([^"]*)"', body)
    return dict(name=name.group(1) if name else '', fields=_list(body, 'fields'), references=_list(body, 'references'))


def read(text: str) -> dict:
    """Models (with fields), enums and the datasource provider of one schema text."""
    models, enums, provider, block, errors = [], [], '', None, []
    datasource = False

    def close(end):
        body = '\n'.join(block.pop('text'))
        block['end'] = end
        block['fp'] = hashlib.sha256(' '.join(body.split()).encode()).hexdigest()[:20]
        (enums if block['kind'] == 'enum' else models).append(block)

    for number, raw in enumerate(text.splitlines(), 1):
        line = _strip_comment(raw)
        if block is not None and BLOCK.match(line):
            errors.append(f"line {number}: {block['kind']} {block['name']} (line {block['line']}) has no closing brace")
            close(number - 1)
            block = None
        if block is None:
            if re.match(r'^\s*datasource\s+\w+\s*\{', line):
                datasource = True
                continue
            if datasource:
                if (found := re.match(r'^\s*provider\s*=\s*"([^"]*)"', line)):
                    provider = found.group(1)
                if line.strip() == '}':
                    datasource = False
                continue
            if (found := BLOCK.match(line)):
                kind, name = found.groups()
                block = dict(kind=kind, name=name, line=number, end=number, table=name, mapped=False, fields=[], text=[])
            continue
        block['text'].append(line)
        if line.strip() == '}':
            close(number)
            block = None
            continue
        stripped = line.strip()
        if not stripped:
            continue
        if block['kind'] == 'enum':
            if not stripped.startswith('@@'):
                block['fields'].append(dict(name=stripped.split()[0], line=number))
            continue
        if stripped.startswith('@@'):
            if (found := BLOCK_MAP.search(stripped)):
                block['table'], block['mapped'] = found.group(1), True
            continue
        found = FIELD.match(line)
        if not found:
            continue
        name, kind, many, optional, attributes = found.groups()
        attributes = attributes or ''
        mapped = MAP.search(attributes)
        block['fields'].append(dict(name=name, type=kind, list=bool(many), optional=bool(optional), line=number,
                                    column=mapped.group(1) if mapped else name, mapped=bool(mapped),
                                    relation=relation(attributes), attributes=attributes.strip(),
                                    on_delete=on_delete.group(1) if (on_delete := ON_DELETE.search(attributes)) else ''))
    if block is not None:
        errors.append(f"{block['kind']} {block['name']} (line {block['line']}) has no closing brace")
        close(len(text.splitlines()))
    return dict(kind='prisma', provider=provider, models=models, enums=enums, errors=errors)


def extract(root, rel, data, module, is_test):
    from flowguard.map.common import normalize_newlines
    from .common import blank
    from .registry import language_for
    out = blank(module, data, language_for(rel), parser=dict(engine='flowguard', grammar='prisma-schema', version='1'))
    text = normalize_newlines(data).decode('utf-8-sig', errors='replace')
    schema = read(text)
    if schema['errors']:
        out['parse_error'] = '; '.join(schema['errors'])
    for item in schema['models'] + schema['enums']:
        out['nodes'].append(dict(qual=item['name'], kind='enum' if item['kind'] == 'enum' else 'model', cls='',
                                 line=item['line'], end=item['end'], column=1, end_column=1,
                                 sig=f"{item['kind']} {item['name']}" + (f" @@map(\"{item['table']}\")" if item.get('mapped') else ''),
                                 doc='', fp=item['fp'], shape=[], size=len(item['fields']),
                                 raw=dict(name=item['name'], table=item.get('table', item['name']))))
    for model in schema['models']:
        out['keys'].append(('model', model['name'], model['line'], model['name']))
        out['keys'].append(('table', model['table'], model['line'], model['name']))
    out['schema'] = schema
    return out


# ---- binding Prisma client writes to models ----------------------------------------------------

def lower_first(name: str) -> str:
    return name[:1].lower() + name[1:]


class Models:
    """Every mapped schema's models by name; a model described by several schemas keeps each."""

    def __init__(self, schemas):
        self.by_name: dict[str, list[dict]] = {}
        for file, schema in schemas:
            for model in schema.get('models', []):
                if model['kind'] in ('model', 'view'):
                    self.by_name.setdefault(model['name'], []).append(dict(model, file=file))
        self.by_accessor = {lower_first(name): name for name in self.by_name}
        self.by_table = {}
        for name, descriptions in self.by_name.items():
            for description in descriptions:
                for key in {description['table'].casefold(), name.casefold()}:
                    self.by_table.setdefault(key, set()).add(name)

    def table_model(self, table):
        found = self.by_table.get((table or '').casefold(), set())
        return next(iter(found)) if len(found) == 1 else None

    def column_field(self, model, column):
        for description in self.by_name.get(model, []):
            for field in description['fields']:
                if is_column(field, self.by_name) and column.casefold() in (field['column'].casefold(), field['name'].casefold()):
                    return field
        return None

    def field(self, model: str, name: str):
        for description in self.by_name.get(model, []):
            for field in description['fields']:
                if field['name'] == name:
                    return field, description
        return None, None

    def children(self, parent: str):
        """[(child model, relation field, key fields, onDelete, required)] of every relation whose foreign key
        (on the child) references `parent`; one row per child relation, whichever schema describes it."""
        found = {}
        for name, descriptions in self.by_name.items():
            for description in descriptions:
                for field in description['fields']:
                    rel = field.get('relation') or {}
                    if field['type'] == parent and rel.get('fields'):
                        found.setdefault((name, field['name']), (name, field['name'], tuple(rel['fields']),
                                                                field.get('on_delete', ''), not field['optional'],
                                                                description['file'], field['line']))
        return [found[key] for key in sorted(found)]

    def is_relation(self, field) -> bool:
        return field is not None and (field['type'] in self.by_name or field.get('relation') is not None)

    def foreign_keys(self, model: str, field):
        """(model holding the key, key fields) of relation `field` on `model`."""
        rel = field.get('relation') or {}
        if rel.get('fields'):
            return model, rel['fields']
        name = rel.get('name', '')
        for description in self.by_name.get(field['type'], []):
            for other in description['fields']:
                other_rel = other.get('relation') or {}
                if other['type'] == model and other_rel.get('fields') and other_rel.get('name', '') == name:
                    return field['type'], other_rel['fields']
        return None, []


def bind(rows, models: Models):
    """Writes with model, field and column, from one reader's Prisma path rows (one row per written
    field per call: the first path that reaches it keeps its position)."""
    out, seen = [], set()
    for row in rows:
        base = {key: row[key] for key in ('node', 'function', 'file', 'line', 'column', 'call_line') if key in row}
        base.update(how='prisma', method=row['method'], receiver=row.get('receiver', ''), accessor=row['accessor'])
        model = models.by_accessor.get(row['accessor'])
        kind = row['method'] + (':' + row['branch'] if row.get('branch') else '')
        if model is None:
            found = [dict(base, model=None, field=row['path'][0] if row['path'] else '*', db_column=None, table=None,
                          kind=kind, nested=False, unclear=True, schema=None,
                          reason=f"accessor {row['accessor']!r} names no model in a mapped Prisma schema")]
        else:
            written = {key: row[key] for key in ('values', 'refs') if key in row}
            found = _walk(base, models, model, row['path'], row['leaf'], kind, row.get('reason', ''), written)
        for item in found:
            key = (item['file'], item.get('call_line'), item['model'], item['field'], item['kind'])
            if key not in seen:
                seen.add(key)
                out.append(item)
    return out


def _write(base, models, model, field_name, kind, *, unclear=False, reason='', nested=False, written=None):
    field, description = models.field(model, field_name)
    table = (description or (models.by_name.get(model) or [{}])[0]).get('table')
    if field is None and field_name not in ('*', '?'):
        reason = reason or f'{model}.{field_name} is not a field of the mapped schema'
    return dict(base, model=model, field=field_name, db_column=field['column'] if field else None, table=table,
                kind=kind, nested=nested, unclear=unclear, reason=reason,
                schema=(description or {}).get('file'), **(written or {}))


CREATING = {'create', 'createMany', 'upsert', 'connectOrCreate'}


def _walk(base, models, model, path, leaf, kind, reason, written=None):
    """Follow [field, op, field, op, ..., field|op] through relations; '...' is a spread at that level."""
    out, nested, op, i = [], False, '', 0
    opaque = reason or 'written value is not an object literal'
    while i < len(path):
        name = path[i]
        if name == '...':
            return out + [_write(base, models, model, '?', kind, unclear=True, nested=nested,
                                 reason=reason or 'spread object: written fields are not visible')]
        if i == len(path) - 1:
            return out + [_write(base, models, model, name, kind, nested=nested, written=written)]
        op = path[i + 1]
        field, _ = models.field(model, name)
        if not models.is_relation(field):
            return out + [_write(base, models, model, name, kind, nested=nested, written=written)]   # {increment: 1}, {set: v}
        holder, keys = models.foreign_keys(model, field)
        if op in CONNECTING or op in CREATING:
            if holder is None:
                out.append(_write(base, models, model, name, op if op in CONNECTING else 'nested:' + op, unclear=True,
                                  nested=True, reason=f'{model}.{name}: no @relation(fields: [...]) on either side '
                                                      '(implicit join table)'))
            else:
                out += [_write(base, models, holder, key, op if op in CONNECTING else 'nested:' + op, nested=True)
                        for key in keys]
        if op in CONNECTING and op != 'connectOrCreate':
            return out
        model, kind, nested = field['type'], 'nested:' + op, True
        i += 2
    if leaf in ('opaque', 'spread'):
        out.append(_write(base, models, model, '?', kind, unclear=True, nested=nested, reason=opaque))
    elif leaf == 'delete' or op in ('delete', 'deleteMany'):
        out.append(_write(base, models, model, '*', kind, nested=nested))
    return out


def bind_sql(rows, models: Models):
    """SQL write statements as writes: the table names a model through @@map or its name, a column a
    field through @map or its name; unknown names stay as written, with no model. A statement in a .sql
    file is not called from anywhere: its call line is its own line, as every write row has one."""
    out = []
    for row in rows:
        base = {key: row[key] for key in ('node', 'function', 'file', 'line', 'column') if key in row}
        base['call_line'] = row['call_line'] if 'call_line' in row else row['line']
        model = models.table_model(row.get('table'))
        values = row.get('values', {})
        for name in row['columns']:
            field = models.column_field(model, name) if model and name != '*' else None
            if name in values:                       # the literal the statement writes, only when spelled
                base_value = dict(base, value=values[name])
            else:
                base_value = base
            out.append(dict(base_value, how='sql', method=row['statement'], kind='sql:' + row['statement'], model=model,
                            field=field['name'] if field else ('*' if name == '*' else None), table=row.get('table'),
                            db_column=name, nested=False, unclear=bool(row.get('unclear')) or name == '*' and row['statement'] != 'delete',
                            reason=row.get('reason') or ('' if model or not row.get('table') else
                                                         f"table {row['table']!r} names no model in a mapped Prisma schema"),
                            schema=None, receiver=row.get('receiver', '')))
    return out


def is_column(field, model_names) -> bool:
    """A scalar, enum or Unsupported(...) field; a relation to an unmapped model (`T[]`, `@relation`) is not."""
    if field['type'] in SCALARS or field['type'].startswith('Unsupported('):
        return True
    return field['type'] not in model_names and field.get('relation') is None and not field['list']


def prisma_tables(schema, model_names) -> dict:
    """{table: {name, model, file, line, columns}} of one Prisma schema; relation fields have no column."""
    out = {}
    for model in schema.get('models', []):
        if model['kind'] != 'model':
            continue
        columns = {f['column'].casefold(): f['column'] for f in model['fields'] if is_column(f, model_names)}
        out[model['table'].casefold()] = dict(name=model['table'], model=model['name'], file=schema['file'],
                                              line=model['line'], columns=columns)
    return out


def gaps(schemas) -> list[dict]:
    """Missing columns (and, for a near-complete description, missing tables) between descriptions."""
    from .sql import describe
    prisma = [schema for schema in schemas if schema.get('kind') == 'prisma']
    names = {model['name'] for schema in prisma for model in schema.get('models', [])}
    described = [(schema['file'], prisma_tables(schema, names)) for schema in prisma]
    sql = [(item['description'], item['tables']) for item in describe(schemas)]
    out = []

    def compare(left_id, left, right_id, right, kind):
        common = set(left) & set(right)
        for key in sorted(common):
            a, b = left[key], right[key]
            missing = sorted(name for cf, name in a["columns"].items() if cf not in b["columns"])
            extra = sorted(name for cf, name in b['columns'].items() if cf not in a['columns'])
            if missing or extra:
                out.append(dict(kind=kind, table=a['name'], model=a.get('model'), schema=left_id, description=right_id,
                                file=b['file'], line=b['line'], missing=missing, extra=extra))
        if 2 * len(common) >= len(left) and common:
            for key in sorted(set(left) - set(right)):
                out.append(dict(kind=kind + '-table', table=left[key]['name'], model=left[key].get('model'), schema=left_id,
                                description=right_id, file=None, line=None, missing=['<table>'], extra=[]))

    for ident, tables in sql:
        # The schema sharing the most tables; on a tie, the one describing those tables with the most columns
        # (a projection that names fewer of them is not what the SQL describes).
        overlap = [(len(set(tables) & set(model_tables)),
                    sum(len(model_tables[key]['columns']) for key in set(tables) & set(model_tables)), file, model_tables)
                   for file, model_tables in described]
        best = max(((count, width) for count, width, _, _ in overlap), default=(0, 0))
        for count, width, file, model_tables in overlap:
            if count and (count, width) == best:
                compare(file, model_tables, ident, tables, 'sql')
    for i, (file, tables) in enumerate(described):
        for other, other_tables in described[i + 1:]:
            if set(tables) & set(other_tables):
                compare(file, tables, other, other_tables, 'prisma')
    return out
