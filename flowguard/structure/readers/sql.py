"""SQL text facts: tables and columns a script declares, and the rows a statement writes.

One small statement reader serves `.sql` files and SQL text found in TS/JS calls such as
Prisma `$executeRaw`. It reads `CREATE TABLE`, `ALTER TABLE ... ADD/DROP/RENAME/ALTER COLUMN`,
`ALTER TABLE ... RENAME TO`, `DROP TABLE`, `INSERT INTO`, `UPDATE ... SET` and `DELETE FROM`,
with plain, `"quoted"`, `` `quoted` `` and
T-SQL `[bracketed]` names. It never executes SQL and does not claim full dialect coverage:
an unrecognized statement contributes no fact, and a column list it cannot read is `*`.
A statement inside a string literal (`EXEC(N'ALTER TABLE ...')`, `SET @sql = N'...'`, `'...'`, `E'...'`)
is SQL built at run time and is not read; a CREATE TABLE there is `unread`, a table it may create.
"""
from __future__ import annotations

import bisect
import hashlib
import re

NAME = r'(?:\[[^\]]+\]|"[^"]+"|`[^`]+`|[A-Za-z_#@][\w$#@]*)'
QUALIFIED = rf'{NAME}(?:\s*\.\s*{NAME}){{0,2}}'
CLAUSES = {'add', 'alter', 'drop', 'rename', 'set', 'enable', 'disable', 'with', 'nocheck', 'owner', 'validate'}
KEEPS_TYPE = {'set', 'drop', 'add', 'reset', 'restart'}     # the words after ALTER COLUMN c that name no new type
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


_CLOSE = {'"': '"', '[': ']', '`': '`'}


def _lexemes(text: str) -> list[tuple[str, int, int]]:
    """[(kind, start, end)] of the comments, string literals and quoted identifiers of SQL, in order: `--` to the
    line's end and `/* */` (kind 'comment'); `'...'` with doubled quotes (kind 'string'; an `E'...'` also takes
    backslash escapes, and in a plain string a `\\'` before a letter or digit is MySQL's escaped quote, so
    `'O\\'Brien'` is one string while `'C:\\'` still ends at its quote); `"..."`, `[...]` and `` `...` ``
    (kind 'identifier', their quote doubled inside), so an apostrophe in a quoted name opens no string. An
    unclosed one runs to the end."""
    out, i, n = [], 0, len(text)
    while i < n:
        two, ch = text[i:i + 2], text[i]
        if two == '--':
            end = text.find('\n', i)
            end = n if end < 0 else end
            out.append(('comment', i, end))
            i = end
        elif two == '/*':
            end = text.find('*/', i + 2)
            end = n if end < 0 else end + 2
            out.append(('comment', i, end))
            i = end
        elif ch == "'":
            escapes = i > 0 and text[i - 1] in 'eE' and (i < 2 or not (text[i - 2].isalnum() or text[i - 2] == '_'))
            end = i + 1
            while end < n:
                if text[end] == '\\' and end + 1 < n and (escapes or (text[end + 1] == "'" and text[end + 2:end + 3].isalnum())):
                    end += 2
                    continue
                if text[end] == "'" and text[end + 1:end + 2] == "'":
                    end += 2
                    continue
                if text[end] == "'":
                    break
                end += 1
            out.append(('string', i, min(end + 1, n)))
            i = end + 1
        elif ch in _CLOSE:
            close, end = _CLOSE[ch], i + 1
            while end < n:
                if text[end] == close and text[end + 1:end + 2] == close:
                    end += 2
                    continue
                if text[end] == close:
                    break
                end += 1
            out.append(('identifier', i, min(end + 1, n)))
            i = end + 1
        else:
            i += 1
    return out


def blank_comments(text: str) -> str:
    """Comments become spaces (newlines kept), so offsets and line numbers stay those of the source. String
    literals and quoted identifiers stay as they are (`_lexemes` tells them apart; `string_spans` finds the
    strings)."""
    out, at = [], 0
    for kind, start, end in _lexemes(text):
        if kind == 'comment':
            out.append(text[at:start])
            out.append(re.sub(r'[^\n]', ' ', text[start:end]))
            at = end
    out.append(text[at:])
    return ''.join(out)


def string_spans(source: str) -> list[tuple[int, int]]:
    """[(start, end)] of the string literals of comment-blanked SQL (`blank_comments`), as `_lexemes` reads them:
    an `N'...'` or `E'...'` prefix is outside the span, a quoted identifier is no string."""
    return [(start, end) for kind, start, end in _lexemes(source) if kind == 'string']


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
    """End of an ALTER clause list: a semicolon, `GO`, or a new line that starts another statement (a line that
    begins `ALTER COLUMN` continues the list, as Prisma writes `ALTER TABLE "t" ALTER COLUMN "a" ...,` and the next
    column on the line below)."""
    semi = text.find(';', start)
    stop = re.compile(r'\n\s*(?:go\b|if\b|alter\b(?!\s+column\b)|create\b|insert\b|update\b|delete\b|drop\b|exec\b|end\b|begin\b'
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


NUMBER = r'[+-]?\d+(?:\.\d+)?'
FLIPPED = {'>=': '<=', '>': '<', '<=': '>=', '<': '>'}


def _bare(body: str) -> str:
    body = body.strip()
    while body.startswith('(') and balanced(body, 0) == len(body):
        body = body[1:-1].strip()
    return body


def ranges(source: str, start: int, end: int) -> list[dict]:
    """`CHECK (col >= 0 AND col <= 2)` or `CHECK (col BETWEEN 0 AND 2)` groups that open between `start` and
    `end`: the column and its numeric bounds as the source spells them (`low`, `high`, either may be absent), each
    inclusive or not. A check that compares another column, a value that is not a number or an OR is no range."""
    found = []
    for match in CHECK.finditer(source, start, end):
        closing = balanced(source, match.end() - 1)
        if closing < 0:
            continue
        body = _bare(source[match.end():closing - 1])
        between = re.fullmatch(rf'({NAME})\s+between\s+({NUMBER})\s+and\s+({NUMBER})', body, re.I)
        if between:
            found.append(dict(column=unquote(between.group(1)), low=between.group(2), high=between.group(3),
                              low_inclusive=True, high_inclusive=True, offset=match.start()))
            continue
        column, bounds = None, {}
        for term in re.split(r'\s+and\s+', body, flags=re.I):
            term = _bare(term)
            plain = re.fullmatch(rf'({NAME})\s*(>=|>|<=|<)\s*({NUMBER})', term)
            flipped = re.fullmatch(rf'({NUMBER})\s*(>=|>|<=|<)\s*({NAME})', term)
            if plain:
                name, operator, number = plain.group(1), plain.group(2), plain.group(3)
            elif flipped:
                name, operator, number = flipped.group(3), FLIPPED[flipped.group(2)], flipped.group(1)
            else:
                break
            if column not in (None, unquote(name)):
                break
            column = unquote(name)
            side = 'low' if operator in ('>=', '>') else 'high'
            bounds[side], bounds[side + '_inclusive'] = number, operator in ('>=', '<=')
        else:
            if column and bounds:
                found.append(dict(column=column, **bounds, offset=match.start()))
    return found


def _range_rows(text: str, row: dict) -> list[dict]:
    return [dict({key: value for key, value in item.items() if key != 'offset'}, line=line_of(text, item['offset']))
            for item in row.get('ranges', ())]


def _column(part: str, at: int):
    match = re.match(NAME, part)
    if not match or match.group(0).lower() in CONSTRAINTS:
        return None
    rest = part[match.end():].split()
    return dict(name=unquote(match.group(0)), offset=at, type=rest[0] if rest else '')


def statements(text: str) -> list[dict]:
    """Write and definition statements: verb, schema, table, columns (name, offset), offset. A statement that
    begins inside a string literal (`string_spans`: `EXEC(N'ALTER TABLE ...')`, `SET @sql = N'ALTER TABLE [t] ADD
    [c] ' + @type`) is SQL built at run time and gives no columns, CHECK or write (Z-5); a CREATE TABLE there is
    `unread`, as a table name built at run time is."""
    source = blank_comments(text)
    spans = string_spans(source)
    starts = [start for start, _ in spans]
    out = []
    for match in STATEMENT.finditer(source):
        verb = ' '.join(match.group('verb').lower().split())
        schema, table = split_name(match.group('table'))
        after = match.end()
        row = dict(verb=verb.split()[0], schema=schema, table=table, offset=match.start(), columns=[], drop=[], retype=[])
        inside = bisect.bisect_left(starts, match.start()) - 1          # the last string opening before it
        if inside >= 0 and match.start() < spans[inside][1]:
            if verb.startswith('create'):
                out.append(dict(row, verb='unread'))
            continue
        if verb.startswith('create'):
            row['verb'] = 'create'
            opening = source.find('(', after)
            closing = balanced(source, opening) if opening >= 0 and not source[after:opening].strip() else -1
            if closing < 0:
                # CREATE TABLE t AS SELECT: the table is spelled, its columns are not (`copy`); a name built at run
                # time (N'CREATE TABLE [dbo].' + QUOTENAME(@t)): not even the table is (`unread`).
                out.append(dict(row, verb='copy' if re.match(r'\s+as\b', source[after:], re.I) else 'unread'))
                continue
            row['columns'] = [c for part, at in top_level(source[opening + 1:closing - 1], opening + 1)
                              if (c := _column(part, at))]
            row['checks'] = checks(source, opening, closing)
            row['ranges'] = ranges(source, opening, closing)
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
                elif head == 'alter' and len(words) > 1 and words[1].lower() == 'column':
                    # A new type (Z-4): Postgres `ALTER COLUMN c TYPE t` (or `SET DATA TYPE t`), T-SQL `ALTER COLUMN
                    # [c] t NULL`; `SET NOT NULL`, `DROP DEFAULT`, `ADD ROWGUIDCOL` and the like keep the type.
                    found = re.match(rf'\s*alter\s+column\s+({NAME})\s+((?:set\s+data\s+)?type\s+)?(\S+)', part, re.I)
                    if found and (found.group(2) or found.group(3).lower() not in KEEPS_TYPE):
                        row['retype'].append(dict(name=unquote(found.group(1)), offset=at, type=found.group(3)))
                elif head == 'rename' and len(words) > 1 and words[1].lower() == 'to':
                    found = re.match(rf'\s*rename\s+to\s+({QUALIFIED})', part, re.I)
                    if found:                           # SQLite's rebuild: ALTER TABLE "new_t" RENAME TO "t"
                        row['rename'] = split_name(found.group(1))[1]
                elif row['columns'] and head not in CONSTRAINTS | CLAUSES and (c := _column(part, at)):
                    row['columns'].append(c)            # T-SQL: ALTER TABLE t ADD a INT, b INT
            row['checks'] = checks(source, after, end)
            row['ranges'] = ranges(source, after, end)
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
    """Tables and columns a SQL file declares (create, alter add/drop/rename, drop, and a column's new type by an
    alter column, `retype`), the tables a CREATE TABLE ... AS SELECT copies (a `copy` change: columns unread), the
    lines of CREATE TABLE statements whose table is not spelled or that a string literal holds (`unread`) and its
    write statements."""
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
                                       for c in row.get('checks', ())], ranges=_range_rows(text, row)))
            out['nodes'].append(dict(qual=qual, kind='table', cls='', line=line, end=end, column=1, end_column=1,
                                     sig=' '.join(body.split())[:160], doc='',
                                     fp=hashlib.sha256(' '.join(body.lower().split()).encode()).hexdigest()[:20],
                                     shape=[], size=len(columns), raw=dict(name=row['table'], schema=row['schema'])))
            out['keys'].append(('table', row['table'], line, ''))
            out['keys'] += [('column', row['table'] + '.' + c['name'], c['line'], '') for c in columns]
        elif row['verb'] == 'copy':
            changes.append(dict(verb='copy', table=row['table'], schema=row['schema'], line=line, add=[], drop=[], checks=[]))
        elif row['verb'] in ('alter', 'drop'):
            changes.append(dict(verb=row['verb'], table=row['table'], schema=row['schema'], line=line,
                                add=columns, drop=row['drop'], **({'rename': row['rename']} if 'rename' in row else {}),
                                retype=[dict(name=c['name'], line=line_of(text, c['offset']), type=c['type'])
                                        for c in row['retype']],
                                checks=[dict(column=c['column'], values=c['values'], line=line_of(text, c['offset']))
                                        for c in row.get('checks', ())], ranges=_range_rows(text, row)))
            out['keys'] += [('column', row['table'] + '.' + c['name'], c['line'], '') for c in columns]
        else:
            out['writes'].append(dict(node=module, file=rel, line=line, via='sql', statement=row['verb'], function='<module>',
                                      table=row['table'], schema=row['schema'],
                                      columns=[c['name'] for c in columns] or ['*']))
    out['schema'] = dict(kind='sql', tables=tables, changes=changes, unread=unread)
    return out


def named(schema) -> dict:
    """{table casefolded: (table, {column casefolded: column})} of the tables and columns one SQL file's statements
    name (its `extract` schema facts), as each statement spells them: a CREATE TABLE's table and its columns, an ALTER
    TABLE's table (and the table it renames it to) with the columns it adds, drops or retypes and those its CHECKs and
    ranges read, a dropped or copied table. A statement in a comment names nothing. A site on a .sql file names one
    of these (`sources.site_resolver`)."""
    found = {}

    def name(table, columns=()):
        _, held = found.setdefault(table.casefold(), (table, {}))
        for column in columns:
            held.setdefault(column.casefold(), column)

    for table in schema['tables']:
        name(table['name'], [column['name'] for column in table['columns']]
             + [item['column'] for item in [*table['checks'], *table['ranges']]])
    for change in schema['changes']:
        if change['verb'] == 'copy':        # CREATE TABLE ... AS SELECT: its columns are not spelled
            name(change['table'])
            continue
        name(change['table'], [*(column['name'] for column in [*change['add'], *change['retype']]), *change['drop'],
                               *(item['column'] for item in [*change['checks'], *change['ranges']])])
        if 'rename' in change:
            name(change['rename'])
    return found


MIGRATION = re.compile(r'^(?P<folder>(?:.*/)?migrations)/[^/]+/migration\.sql$', re.I)


def describe(schemas) -> list[dict]:
    """SQL descriptions of tables: each .sql file alone, except Prisma `migrations/<name>/migration.sql`
    files, which are applied in folder order as one description. A table counts only once a
    CREATE TABLE in the description defines it (a CREATE TABLE ... AS SELECT with columns None: they are not
    spelled); ALTER ADD/DROP COLUMN, ALTER ... RENAME TO (SQLite's `CREATE TABLE "new_t"`, `DROP TABLE "t"`,
    `ALTER TABLE "new_t" RENAME TO "t"`) and DROP TABLE then change it. `altered` holds the columns an ALTER
    ADD (or RENAME COLUMN) of the description gives a table it does not define, as an upgrade script does to a
    table another file creates: {table: {column: name}}, casefolded keys as in `tables`; `added` the same columns of
    an ALTER ADD with their declaration, {table: {column: {table, name, type, file, line}}}. A table's `declared` holds
    each column's last declaration in the description, {column: {type, file, line}}: a rebuild's CREATE TABLE
    "new_t" replaces the one before it, an ALTER ADD adds one, a RENAME COLUMN keeps the type it renames, and an ALTER
    COLUMN that gives a column of the table a type (`retype`: `ALTER COLUMN c TYPE t`, T-SQL `ALTER COLUMN [c] t`)
    declares that type there (Z-4)."""
    grouped = {}
    for schema in schemas:
        if schema.get('kind') != 'sql':
            continue
        found = MIGRATION.match(schema['file'])
        grouped.setdefault(found.group('folder') + '/' if found else schema['file'], []).append(schema)
    out = []
    for ident, members in sorted(grouped.items()):
        tables, altered, added = {}, {}, {}
        for schema in sorted(members, key=lambda item: item['file']):
            events = [('create', t['line'], t) for t in schema['tables']] + [(c['verb'], c['line'], c) for c in schema['changes']]
            for verb, _, item in sorted(events, key=lambda event: event[1]):
                key = item.get('name', item.get('table', '')).casefold()
                if verb == 'create':
                    tables[key] = dict(name=item['name'], file=schema['file'], line=item['line'],
                                       columns={c['name'].casefold(): c['name'] for c in item['columns']}, checks={},
                                       declared={c['name'].casefold(): dict(type=c['type'], file=schema['file'], line=c['line'])
                                                 for c in item['columns']})
                elif verb == 'drop':
                    tables.pop(item['table'].casefold(), None)
                elif verb == 'copy':
                    tables[key] = dict(name=item['table'], file=schema['file'], line=item['line'], columns=None, checks={},
                                       declared={})
                elif key in tables and tables[key]['columns'] is not None:
                    columns, declared = tables[key]['columns'], tables[key]['declared']
                    dropped = [declared.pop(name.casefold(), None) for name in item['drop']]
                    for name in item['drop']:
                        columns.pop(name.casefold(), None)
                    columns.update((c['name'].casefold(), c['name']) for c in item['add'])
                    renamed = dropped[0]['type'] if len(dropped) == 1 and dropped[0] is not None else ''
                    declared.update((c['name'].casefold(), dict(type=c['type'] or renamed, file=schema['file'], line=c['line']))
                                    for c in item['add'])
                    declared.update((c['name'].casefold(), dict(type=c['type'], file=schema['file'], line=c['line']))
                                    for c in item['retype'] if c['name'].casefold() in columns)
                elif key not in tables:             # an upgrade script's ALTER ADD of a table created elsewhere
                    altered.setdefault(key, {}).update((c['name'].casefold(), c['name']) for c in item['add'])
                    added.setdefault(key, {}).update((c['name'].casefold(), dict(table=item.get('table') or item['name'], name=c['name'],
                                                                                 type=c['type'], file=schema['file'],
                                                                                 line=c['line'])) for c in item['add'])
                if key in tables:                   # a later CHECK on a column replaces an earlier one
                    tables[key]['checks'].update((c['column'].casefold(), dict(c, file=schema['file']))
                                                 for c in item.get('checks', ()))
                if verb == 'alter' and 'rename' in item and key in tables:
                    tables[item['rename'].casefold()] = dict(tables.pop(key), name=item['rename'])
        # A CREATE TABLE whose table is not spelled may create any table: such a description lacks no table.
        out.append(dict(description=ident, files=sorted(item['file'] for item in members), tables=tables,
                        altered=altered, added=added, partial=any(schema['unread'] for schema in members)))
    return out
