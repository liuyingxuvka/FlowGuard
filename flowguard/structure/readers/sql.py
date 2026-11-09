"""SQL text facts: tables and columns a script declares, and the rows a statement writes.

One small statement reader serves `.sql` files and SQL text found in TS/JS calls such as
Prisma `$executeRaw`. It reads `CREATE TABLE`, `ALTER TABLE ... ADD/DROP/RENAME COLUMN`,
`ALTER TABLE ... RENAME TO`, `DROP TABLE`, `INSERT INTO`, `UPDATE ... SET` and `DELETE FROM`,
with plain, `"quoted"`, `` `quoted` `` and
T-SQL `[bracketed]` names. It never executes SQL and does not claim full dialect coverage:
an unrecognized statement contributes no fact, and a column list it cannot read is `*`.
"""
from __future__ import annotations

import hashlib
import re

NAME = r'(?:\[[^\]]+\]|"[^"]+"|`[^`]+`|[A-Za-z_#@][\w$#@]*)'
QUALIFIED = rf'{NAME}(?:\s*\.\s*{NAME}){{0,2}}'
CLAUSES = {'add', 'alter', 'drop', 'rename', 'set', 'enable', 'disable', 'with', 'nocheck', 'owner', 'validate'}
CONSTRAINTS = {'constraint', 'primary', 'foreign', 'unique', 'check', 'index', 'key', 'period', 'exclude', 'like'}
ENDS = re.compile(r'\b(?:where|from|output|returning|option)\b', re.I)
STATEMENT = re.compile(
    rf'\b(?P<verb>create\s+(?:or\s+replace\s+)?(?:temporary\s+|temp\s+)?table(?:\s+if\s+not\s+exists)?'
    rf'|alter\s+table(?:\s+if\s+exists)?(?:\s+only)?|drop\s+table(?:\s+if\s+exists)?'
    rf'|insert\s+(?:or\s+\w+\s+)?into|insert(?=\s+{NAME}\s*\()|replace\s+into|update|delete\s+from|delete(?=\s+{NAME}\s+where\b)'
    rf'|merge\s+into)\s+(?P<table>{QUALIFIED})', re.I)
LITERAL = re.compile(r"[+-]?(?:\d+\.\d*|\.\d+|\d+)(?:e[+-]?\d+)?|N?'(?:[^']|'')*'|null|true|false", re.I)


def unquote(name: str) -> str:
    name = name.strip()
    if len(name) > 1 and (name[0], name[-1]) in (('[', ']'), ('"', '"'), ('`', '`')):
        return name[1:-1]
    return name


def split_name(qualified: str) -> tuple[str, str]:
    """(schema, table) of `dbo.t`, `[dbo].[t]` or `t`; a database prefix is kept with the schema."""
    parts = [unquote(part) for part in re.findall(NAME, qualified)]
    return '.'.join(parts[:-1]), parts[-1] if parts else ''


def blank_comments(text: str) -> str:
    """Comments become spaces (newlines kept), so offsets and line numbers stay those of the source."""
    out, i, n = [], 0, len(text)
    while i < n:
        two = text[i:i + 2]
        if two == '--':
            end = text.find('\n', i)
            end = n if end < 0 else end
            out.append(' ' * (end - i))
            i = end
        elif two == '/*':
            end = text.find('*/', i + 2)
            end = n if end < 0 else end + 2
            out.append(re.sub(r'[^\n]', ' ', text[i:end]))
            i = end
        elif text[i] == "'":                        # string bodies stay: EXEC(N'ALTER TABLE ...') is SQL too
            end = i + 1
            while end < n:
                if text[end] == "'" and text[end + 1:end + 2] == "'":
                    end += 2
                    continue
                if text[end] == "'":
                    break
                end += 1
            out.append(text[i:end + 1])
            i = end + 1
        else:
            out.append(text[i])
            i += 1
    return ''.join(out)


def balanced(text: str, start: int) -> int:
    """Index just after the parenthesis group that opens at `start`, or -1."""
    depth = 0
    for i in range(start, len(text)):
        if text[i] == '(':
            depth += 1
        elif text[i] == ')':
            depth -= 1
            if depth == 0:
                return i + 1
    return -1


def top_level(text: str, base: int = 0) -> list[tuple[str, int]]:
    """Comma-separated parts outside parentheses and quotes, with their offsets."""
    parts, depth, start, quote = [], 0, 0, ''
    for i, ch in enumerate(text):
        if quote:
            if ch == quote:
                quote = ''
        elif ch in "'\"`[":
            quote = ']' if ch == '[' else ch
        elif ch == '(':
            depth += 1
        elif ch == ')':
            depth -= 1
        elif ch == ',' and depth == 0:
            parts.append((text[start:i], base + start))
            start = i + 1
    parts.append((text[start:], base + start))
    return [(part.strip(), at + len(part) - len(part.lstrip())) for part, at in parts if part.strip()]


def _clause_end(text: str, start: int) -> int:
    """End of an ALTER clause list: a semicolon, `GO`, or a new line that starts another statement."""
    semi = text.find(';', start)
    stop = re.compile(r'\n\s*(?:go\b|if\b|alter\b|create\b|insert\b|update\b|delete\b|drop\b|exec\b|end\b|begin\b'
                      r'|set\b|print\b|commit\b|select\b|\))', re.I).search(text, start)
    ends = [i for i in (semi, stop.start() if stop else -1) if i >= 0]
    return min(ends) if ends else len(text)


def literal(text: str):
    """(True, value) for a SQL number, 'text', NULL, TRUE or FALSE; (False, None) for anything else
    (a placeholder, a column, an expression): a value the statement does not spell is never guessed."""
    text = text.strip()
    if not LITERAL.fullmatch(text):
        return False, None
    low = text.lower()
    if low in ('null', 'true', 'false'):
        return True, None if low == 'null' else low == 'true'
    if text.endswith("'"):
        return True, text[text.index("'") + 1:-1].replace("''", "'")
    number = float(text)
    return True, int(text) if re.fullmatch(r'[+-]?\d+', text) else number


CHECK = re.compile(r'\bcheck\s*\(', re.I)
QUOTED = re.compile(r"N?'((?:[^']|'')*)'", re.I)


def checks(source: str, start: int, end: int) -> list[dict]:
    """`CHECK (col IN ('a', 'b'))` groups that open between `start` and `end`: the column and its closed
    set of string values. A check on anything else (a range, a relation between columns) is not a set.
    Inside `EXEC(N'...')` the doubled quotes of the string are read as single ones."""
    found = []
    for match in CHECK.finditer(source, start, end):
        closing = balanced(source, match.end() - 1)
        if closing < 0:
            continue
        body = source[match.end():closing - 1].replace("''", "'").strip()
        while body.startswith('(') and balanced(body, 0) == len(body):
            body = body[1:-1].strip()
        listed = re.fullmatch(rf'({NAME})\s+in\s*\((.*)\)', body, re.I | re.S)
        if not listed:
            continue
        values = [value.replace("''", "'") for value in QUOTED.findall(listed.group(2))]
        if values and not QUOTED.sub('', listed.group(2)).replace(',', '').strip():
            found.append(dict(column=unquote(listed.group(1)), values=values, offset=match.start()))
    return found


def _column(part: str, at: int):
    match = re.match(NAME, part)
    if not match or match.group(0).lower() in CONSTRAINTS:
        return None
    rest = part[match.end():].split()
    return dict(name=unquote(match.group(0)), offset=at, type=rest[0] if rest else '')


def statements(text: str) -> list[dict]:
    """Write and definition statements: verb, schema, table, columns (name, offset), offset."""
    source = blank_comments(text)
    out = []
    for match in STATEMENT.finditer(source):
        verb = ' '.join(match.group('verb').lower().split())
        schema, table = split_name(match.group('table'))
        after = match.end()
        row = dict(verb=verb.split()[0], schema=schema, table=table, offset=match.start(), columns=[], drop=[])
        if verb.startswith('create'):
            row['verb'] = 'create'
            opening = source.find('(', after)
            closing = balanced(source, opening) if opening >= 0 and not source[after:opening].strip() else -1
            if closing < 0:
                # CREATE TABLE ... AS SELECT, or a name built at run time (N'CREATE TABLE [dbo].' + QUOTENAME(@t)):
                # the table or its columns are not spelled.
                out.append(dict(row, verb='unread'))
                continue
            row['columns'] = [c for part, at in top_level(source[opening + 1:closing - 1], opening + 1)
                              if (c := _column(part, at))]
            row['checks'] = checks(source, opening, closing)
            row['end'] = closing
        elif verb.startswith('alter'):
            row['verb'] = 'alter'
            end = _clause_end(source, after)
            for part, at in top_level(source[after:end], after):
                words = part.split(None, 2)
                head = words[0].lower() if words else ''
                if head == 'add':
                    rest = part[len(words[0]):].lstrip()
                    at += len(part) - len(rest)
                    if rest.lower().startswith('column '):
                        rest, at = rest[7:].lstrip(), at + len(rest) - len(rest[7:].lstrip())
                    if rest.lower().startswith('if not exists '):
                        rest, at = rest[14:].lstrip(), at + len(rest) - len(rest[14:].lstrip())
                    if (c := _column(rest, at)):
                        row['columns'].append(c)
                elif head == 'drop' and len(words) > 1 and words[1].lower() == 'column':
                    names = re.sub(r'^\s*drop\s+column\s+(?:if\s+exists\s+)?', '', part, flags=re.I)
                    row['drop'] += [unquote(n) for n in re.findall(NAME, names)[:1]]
                elif head == 'rename' and len(words) > 1 and words[1].lower() == 'column':
                    found = re.match(rf'\s*rename\s+column\s+({NAME})\s+to\s+({NAME})', part, re.I)
                    if found:
                        row['drop'].append(unquote(found.group(1)))
                        row['columns'].append(dict(name=unquote(found.group(2)), offset=at, type=''))
                elif head == 'rename' and len(words) > 1 and words[1].lower() == 'to':
                    found = re.match(rf'\s*rename\s+to\s+({QUALIFIED})', part, re.I)
                    if found:                           # SQLite's rebuild: ALTER TABLE "new_t" RENAME TO "t"
                        row['rename'] = split_name(found.group(1))[1]
                elif row['columns'] and head not in CONSTRAINTS | CLAUSES and (c := _column(part, at)):
                    row['columns'].append(c)            # T-SQL: ALTER TABLE t ADD a INT, b INT
            row['checks'] = checks(source, after, end)
            row['end'] = end
        elif verb.startswith('drop'):
            row['verb'] = 'drop'
        elif verb.startswith(('insert', 'merge', 'replace')):
            row['verb'] = 'insert'
            rest = source[after:]
            if rest.lstrip().startswith('('):
                opening = after + len(rest) - len(rest.lstrip())
                closing = balanced(source, opening)
                if closing > 0:
                    row['columns'] = [dict(name=unquote(m.group(0)), offset=at + m.start(), type='')
                                      for part, at in top_level(source[opening + 1:closing - 1], opening + 1)
                                      if (m := re.match(NAME, part))]
                    values = re.compile(r'\s*values\s*\(', re.I).match(source, closing)
                    end = balanced(source, values.end() - 1) if values else -1
                    if end > 0:                         # one VALUES row: each spelled literal belongs to its column
                        items = top_level(source[values.end():end - 1])
                        if len(items) == len(row['columns']):
                            for column, (item, _) in zip(row['columns'], items):
                                readable, value = literal(item)
                                if readable:
                                    column['value'] = value
        elif verb == 'update':
            found = re.compile(r'\s+(?:as\s+)?(?:\w+\s+)?set\s', re.I).match(source, after)
            if not found:
                continue
            start = found.end()
            stop = ENDS.search(source, start)
            semi = source.find(';', start)
            end = min(i for i in (stop.start() if stop else len(source), semi if semi >= 0 else len(source)))
            for part, at in top_level(source[start:end], start):
                left, _, right = part.partition('=') if '=' in part else ('', '', '')
                names = re.findall(NAME, left)
                if names:
                    column = dict(name=unquote(names[-1]), offset=at, type='')
                    readable, value = literal(right)
                    if readable:
                        column['value'] = value
                    row['columns'].append(column)
        elif verb.startswith('delete'):
            row['verb'] = 'delete'
        out.append(row)
    return out


def line_of(text: str, offset: int) -> int:
    return text.count('\n', 0, offset) + 1


def extract(root, rel, data, module, is_test):
    """Tables and columns a SQL file declares (create, alter add/drop/rename, drop), the lines of CREATE TABLE
    statements it cannot read (`unread`) and its write statements."""
    from flowguard.map.common import normalize_newlines
    from .common import blank
    from .registry import language_for
    language = language_for(rel)
    out = blank(module, data, language, parser=dict(engine='flowguard', grammar='sql-statements', version='1'))
    text = normalize_newlines(data).decode('utf-8-sig', errors='replace')
    out['source_lines'] = len(text.splitlines())
    tables, changes, unread, used = [], [], [], set()
    for row in statements(text):
        line = line_of(text, row['offset'])
        if row['verb'] == 'unread':
            unread.append(line)
            continue
        columns = [dict(name=c['name'], line=line_of(text, c['offset']), type=c['type']) for c in row['columns']]
        if row['verb'] == 'create':
            qual = row['table'] if row['table'] not in used else row['table'] + '@' + str(line)
            used.add(qual)
            end = line_of(text, row['end'])
            body = text[row['offset']:row['end']]
            tables.append(dict(name=row['table'], schema=row['schema'], line=line, end=end, columns=columns,
                               checks=[dict(column=c['column'], values=c['values'], line=line_of(text, c['offset']))
                                       for c in row.get('checks', ())]))
            out['nodes'].append(dict(qual=qual, kind='table', cls='', line=line, end=end, column=1, end_column=1,
                                     sig=' '.join(body.split())[:160], doc='',
                                     fp=hashlib.sha256(' '.join(body.lower().split()).encode()).hexdigest()[:20],
                                     shape=[], size=len(columns), raw=dict(name=row['table'], schema=row['schema'])))
            out['keys'].append(('table', row['table'], line, ''))
            out['keys'] += [('column', row['table'] + '.' + c['name'], c['line'], '') for c in columns]
        elif row['verb'] in ('alter', 'drop'):
            changes.append(dict(verb=row['verb'], table=row['table'], schema=row['schema'], line=line,
                                add=columns, drop=row['drop'], **({'rename': row['rename']} if 'rename' in row else {}),
                                checks=[dict(column=c['column'], values=c['values'], line=line_of(text, c['offset']))
                                        for c in row.get('checks', ())]))
            out['keys'] += [('column', row['table'] + '.' + c['name'], c['line'], '') for c in columns]
        else:
            out['writes'].append(dict(node=module, file=rel, line=line, via='sql', statement=row['verb'], function='<module>',
                                      table=row['table'], schema=row['schema'],
                                      columns=[c['name'] for c in columns] or ['*']))
    out['schema'] = dict(kind='sql', tables=tables, changes=changes, unread=unread)
    return out


MIGRATION = re.compile(r'^(?P<folder>(?:.*/)?migrations)/[^/]+/migration\.sql$', re.I)


def describe(schemas) -> list[dict]:
    """SQL descriptions of tables: each .sql file alone, except Prisma `migrations/<name>/migration.sql`
    files, which are applied in folder order as one description. A table counts only once a
    CREATE TABLE in the description defines it; ALTER ADD/DROP COLUMN, ALTER ... RENAME TO (SQLite's
    `CREATE TABLE "new_t"`, `DROP TABLE "t"`, `ALTER TABLE "new_t" RENAME TO "t"`) and DROP TABLE then change it."""
    grouped = {}
    for schema in schemas:
        if schema.get('kind') != 'sql':
            continue
        found = MIGRATION.match(schema['file'])
        grouped.setdefault(found.group('folder') + '/' if found else schema['file'], []).append(schema)
    out = []
    for ident, members in sorted(grouped.items()):
        tables = {}
        for schema in sorted(members, key=lambda item: item['file']):
            events = [('create', t['line'], t) for t in schema['tables']] + [(c['verb'], c['line'], c) for c in schema['changes']]
            for verb, _, item in sorted(events, key=lambda event: event[1]):
                key = item.get('name', item.get('table', '')).casefold()
                if verb == 'create':
                    tables[key] = dict(name=item['name'], file=schema['file'], line=item['line'],
                                       columns={c['name'].casefold(): c['name'] for c in item['columns']}, checks={})
                elif verb == 'drop':
                    tables.pop(item['table'].casefold(), None)
                elif key in tables:
                    columns = tables[key]['columns']
                    for name in item['drop']:
                        columns.pop(name.casefold(), None)
                    columns.update((c['name'].casefold(), c['name']) for c in item['add'])
                if key in tables:                   # a later CHECK on a column replaces an earlier one
                    tables[key]['checks'].update((c['column'].casefold(), dict(c, file=schema['file']))
                                                 for c in item.get('checks', ()))
                if verb == 'alter' and 'rename' in item and key in tables:
                    tables[item['rename'].casefold()] = dict(tables.pop(key), name=item['rename'])
        # A CREATE TABLE the reader cannot read may create any table: such a description lacks no table.
        out.append(dict(description=ident, files=sorted(item['file'] for item in members), tables=tables,
                        partial=any(schema['unread'] for schema in members)))
    return out
