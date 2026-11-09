"""Prisma schema and SQL text readers, and string-literal facts that must stay quiet."""
from contextlib import closing

import pytest

from flowguard.structure import build
from flowguard.structure.readers.sql import statements


def project(tmp_path, files):
    for name, content in files.items():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding='utf-8')
    return build(tmp_path, tmp_path / 'map.sqlite', workers=1)


def test_sql_statements_read_brackets_quotes_alter_lists_and_writes():
    found = [(row['verb'], row['schema'], row['table'], [c['name'] for c in row['columns']], row['drop']) for row in statements(
        '-- CREATE TABLE ignored (x INT)\n'
        'CREATE TABLE IF NOT EXISTS "app"."Item" ("id" TEXT NOT NULL, `qty` INT, CONSTRAINT pk PRIMARY KEY ("id"));\n'
        'ALTER TABLE [dbo].[Item] ADD [price] DECIMAL(10, 2) NULL, [note] NVARCHAR(200);\n'
        'ALTER TABLE "Item" ADD COLUMN "tag" TEXT, ADD CONSTRAINT u UNIQUE ("tag"), DROP COLUMN qty;\n'
        "EXEC(N'ALTER TABLE [dbo].[Item] ADD [owner] NVARCHAR(32) NULL;');\n"
        "UPDATE [dbo].[Item] SET [price] = CASE WHEN a IN (1, 2) THEN 1 END, note = 'a, b' WHERE id = 1;\n"
        'INSERT INTO Item (id, qty) VALUES (1, 2);\n'
        'DELETE FROM Item WHERE id = 1;\n'
        'DROP TABLE IF EXISTS Old;\n')]
    assert found == [
        ('create', 'app', 'Item', ['id', 'qty'], []),
        ('alter', 'dbo', 'Item', ['price', 'note'], []),
        ('alter', '', 'Item', ['tag'], ['qty']),
        ('alter', 'dbo', 'Item', ['owner'], []),
        ('update', 'dbo', 'Item', ['price', 'note'], []),
        ('insert', '', 'Item', ['id', 'qty'], []),
        ('delete', '', 'Item', [], []),
        ('drop', '', 'Old', [], []),
    ]


def test_prisma_schema_reads_maps_relations_enums_and_reports_unclosed_blocks(tmp_path):
    with closing(project(tmp_path, {
        'prisma/schema.prisma': '''datasource db {
  provider = "postgresql" // comment
  url      = env("DATABASE_URL")
}
enum Role {
  ADMIN
  USER
}
model Account {
  id      String  @id
  ownerId String  @map("owner_id")
  role    Role    @default(USER)
  owner   User    @relation("Owned", fields: [ownerId], references: [id])
  @@map("accounts")
}
model User {
  id       String    @id
  accounts Account[] @relation("Owned")
}
''',
        'prisma/broken.prisma': 'model Half {\n  id String @id\nmodel Next {\n  id String @id\n}\n',
    })) as graph:
        schema = next(item for item in graph.schemas() if item['file'] == 'prisma/schema.prisma')
        assert schema['provider'] == 'postgresql' and [e['name'] for e in schema['enums']] == ['Role']
        account = schema['models'][0]
        assert (account['name'], account['table']) == ('Account', 'accounts')
        fields = {field['name']: field for field in account['fields']}
        assert fields['ownerId']['column'] == 'owner_id'
        assert fields['owner']['relation'] == dict(name='Owned', fields=['ownerId'], references=['id'])
        assert graph.node('prisma/prisma/schema.prisma:Account')['kind'] == 'model'
        assert graph.node('prisma/prisma/schema.prisma:Role')['kind'] == 'enum'
        broken = next(row for row in graph.capabilities()['languages'].values() if row['errors'])
        assert broken['files'] == 2 and broken['errors'] == 1
        graph.reset_query_coverage()
        graph.schemas()
        coverage = graph.query_coverage()
        assert not coverage['complete'] and coverage['issues'][0]['files'] == ['prisma/broken.prisma']
        assert 'model Half (line 1) has no closing brace' in coverage['issues'][0]['reason']


def test_javascript_writes_and_quiet_literals(tmp_path):
    with closing(project(tmp_path, {
        'schema.prisma': 'model Item {\n  id String @id\n  name String\n  @@map("items")\n}\n',
        'item.js': '''const KEYS = { id: 1, 'ID': 2 };
export async function save(db, item, log) {
  console.warn('Item saved', ['id']);
  if (!item) throw new Error('ID missing');
  await db.item.update({ where: { name: item.name }, select: { id: true }, data: { name: item.name } });
  await db.$executeRawUnsafe(`INSERT INTO items (id, name) VALUES ($1, $2)`, item.id, item.name);
  return item.kind === 'id' ? 'ok' : 'Ok';
}
''',
        'view.tsx': '''type Tone = 'ok' | 'warn';
export function Badge({ load }: { load: () => void }) {
  try { load(); } catch { return <span/>; }
  return <b/>;
}
''',
    })) as graph:
        writes = [(row['model'], row['field'], row['kind']) for row in graph.writes()]
        assert writes == [('Item', 'name', 'update'), ('Item', 'id', 'sql:insert'), ('Item', 'name', 'sql:insert')]
        values = sorted((row['value'], row['context']) for row in graph.literals(language='javascript'))
        assert values == [('Ok', 'return'), ('id', 'compare'), ('ok', 'return')]
        groups = graph.literal_groups()
        assert [group['key'] for group in groups] == ['ok']          # 'id' / 'ID' as keys never group
        assert set(groups[0]['spellings']) == {'ok', 'Ok'}
        assert [(row['value'], row['context']) for row in graph.literals(language='tsx')] == [('ok', 'union'), ('warn', 'union')]
        tsx = graph.handlers(language='tsx')
        assert [(row['type'], row['non_raising'], row['key']) for row in tsx] == [('any', True, 'view.tsx:Badge:any')]


SCHEMA = '''datasource db {
  provider = "%s"
  url      = env("DATABASE_URL")
}
model Item {
  id    String @id
  name  String
  note  String?
  @@map("items")
}
model Order {
  id     String @id
  itemId String @map("item_id")
  @@map("orders")
}
model Log {
  id String @id
  @@map("logs")
}
'''


def test_schema_gaps_follow_rebuilds_skip_archives_and_compare_each_description_once(tmp_path):
    # Planning Tool 0.6.28 had 33 such lines and 2 real ones: a SQLite rebuild read as a missing table, archived
    # SQL under docs/, every description reported once per provider template, and a read-only client schema.
    files = {
        'backend/package.json': '{"name": "backend"}',
        'backend/prisma/schema.prisma': SCHEMA % 'sqlserver',
        'backend/prisma/schema.sqlite.prisma': SCHEMA % 'sqlite',
        'backend/prisma/migrations/1_init/migration.sql':
            'CREATE TABLE "items" ("id" TEXT NOT NULL, "name" TEXT NOT NULL);\n'
            'CREATE TABLE "orders" ("id" TEXT NOT NULL, "item_id" TEXT NOT NULL);\n'
            'CREATE TABLE "logs" ("id" TEXT NOT NULL);\n',
        'backend/prisma/migrations/2_note/migration.sql':
            'CREATE TABLE "new_items" ("id" TEXT NOT NULL, "name" TEXT NOT NULL, "note" TEXT);\n'
            'INSERT INTO "new_items" ("id", "name") SELECT "id", "name" FROM "items";\n'
            'DROP TABLE "items";\n'
            'ALTER TABLE "new_items" RENAME TO "items";\n',
        'backend/prisma/setup.sql':
            'CREATE TABLE [dbo].[items] ([id] NVARCHAR(36) NOT NULL, [name] NVARCHAR(100) NOT NULL);\n'
            'CREATE TABLE [dbo].[orders] ([id] NVARCHAR(36) NOT NULL, [item_id] NVARCHAR(36) NOT NULL);\n',
        'backend/prisma/staged.sql':
            "CREATE TABLE [dbo].[items] ([id] NVARCHAR(36) NOT NULL, [name] NVARCHAR(100) NOT NULL, [note] NVARCHAR(10));\n"
            "SELECT @sql = N'CREATE TABLE [dbo].' + QUOTENAME(@table) + N' (' + @columns + N')';\n",
        'docs/releases/2026/setup.sql': 'CREATE TABLE [dbo].[items] ([id] NVARCHAR(36) NOT NULL);\n',
        'client/package.json': '{"name": "client"}',
        'client/prisma/schema.prisma': '''model Item {
  id   String @id
  name String
  @@map("items")
}
''',
    }
    with closing(project(tmp_path, files)) as graph:
        found = sorted((gap['description'], gap['schema'], gap['kind'], gap['table'], tuple(gap['missing']), tuple(gap['extra']))
                       for gap in graph.schema_gaps())
        # Once, with the schema in use; the rebuilt items table has its note; the CREATE TABLE built at run time in
        # staged.sql may create orders and logs; the archive and the client's projection lack nothing.
        assert found == [
            ('backend/prisma/setup.sql', 'backend/prisma/schema.prisma', 'sql', 'items', ('note',), ()),
            ('backend/prisma/setup.sql', 'backend/prisma/schema.prisma', 'sql-table', 'logs', ('<table>',), ()),
        ], found
        staged = next(row for row in graph.schemas() if row['file'] == 'backend/prisma/staged.sql')
        assert staged['unread'] == [2]
    # A client schema with a column the database lacks is no projection; a template that drifted is compared
    # with the schema in use, not with the other templates.
    (tmp_path / 'client/prisma/schema.prisma').write_text(files['client/prisma/schema.prisma'].replace(
        '  name String\n', '  name String\n  colour String\n'), encoding='utf-8')
    (tmp_path / 'backend/prisma/schema.sqlite.prisma').write_text((SCHEMA % 'sqlite').replace('  note  String?\n', ''),
                                                                   encoding='utf-8')
    (tmp_path / 'backend/prisma/schema.mysql.prisma').write_text(SCHEMA % 'mysql', encoding='utf-8')
    (tmp_path / 'pyproject.toml').write_text('[tool.flowguard]\narchives = []\n', encoding='utf-8')
    with closing(build(tmp_path, tmp_path / 'map.sqlite', workers=1)) as graph:
        found = sorted((gap['description'], gap['schema'], gap['table'], tuple(gap['missing']), tuple(gap['extra']))
                       for gap in graph.schema_gaps() if gap['kind'] in ('sql', 'prisma'))
        assert found == [
            ('backend/prisma/schema.sqlite.prisma', 'backend/prisma/schema.prisma', 'items', ('note',), ()),
            ('backend/prisma/setup.sql', 'backend/prisma/schema.prisma', 'items', ('note',), ()),
            ('client/prisma/schema.prisma', 'backend/prisma/schema.prisma', 'items', ('note',), ('colour',)),
            ('docs/releases/2026/setup.sql', 'backend/prisma/schema.prisma', 'items', ('name', 'note'), ()),
        ], found
    (tmp_path / 'pyproject.toml').write_text('[tool.flowguard]\narchives = "docs"\n', encoding='utf-8')
    with closing(build(tmp_path, tmp_path / 'map.sqlite', workers=1)) as graph:
        with pytest.raises(ValueError, match='archives must be a list of path patterns'):
            graph.schema_gaps()


CENTRAL = '''model Setting {
  id    String @id
  label String
  @@map("settings")
}
model Person {
  id    String @id
  name  String
  email String
  @@map("people")
}
model Unit {
  id    String @id
  title String
  @@map("units")
}
'''


def test_a_copied_table_hides_no_gap_and_a_schema_of_another_database_is_no_reference(tmp_path):
    # A CREATE TABLE ... AS SELECT backup made a whole migrations folder lack no table, so the table it really lacks
    # went unreported; and a second database described only by provider templates was compared with the first
    # database's schema in use because the two share one table name.
    main = (SCHEMA % 'sqlite').replace('model Log {', 'model Setting {\n  id    String @id\n  value String\n'
                                       '  @@map("settings")\n}\nmodel Log {')
    with closing(project(tmp_path, {
        'prisma/schema.prisma': main,
        'prisma/migrations/1_init/migration.sql':
            'CREATE TABLE "items" ("id" TEXT NOT NULL, "name" TEXT NOT NULL, "note" TEXT);\n'
            'CREATE TABLE "orders" ("id" TEXT NOT NULL, "item_id" TEXT NOT NULL);\n'
            'CREATE TABLE "settings" ("id" TEXT NOT NULL, "value" TEXT NOT NULL);\n',
        'prisma/migrations/2_backup/migration.sql': 'CREATE TABLE "items_backup" AS SELECT * FROM "items";\n',
        'prisma/rebuild.sql':
            'CREATE TABLE items (id TEXT, note TEXT);\nCREATE TABLE orders (id TEXT, item_id TEXT);\n'
            'CREATE TABLE settings (id TEXT, value TEXT);\n'
            'CREATE TABLE new_logs AS SELECT id FROM old_logs;\nALTER TABLE new_logs RENAME TO logs;\n'
            'ALTER TABLE logs ADD COLUMN extra TEXT;\n',
        'prisma/central/schema.sqlite.prisma': CENTRAL,
        'prisma/central/schema.sqlserver.prisma': CENTRAL,
        'prisma/central/init.sql': 'CREATE TABLE settings (id TEXT, label TEXT);\nCREATE TABLE people (id TEXT, name TEXT);\n'
                                   'CREATE TABLE units (id TEXT, title TEXT);\n',
    })) as graph:
        found = sorted((gap['description'], gap['schema'], gap['kind'], gap['table'], tuple(gap['missing']), tuple(gap['extra']))
                       for gap in graph.schema_gaps())
        # The backup copy names its table, so the folder still lacks logs; the copy renamed to logs in rebuild.sql
        # is that table, its columns unread; init.sql describes the second database's templates.
        assert found == [
            ('prisma/central/init.sql', 'prisma/central/schema.sqlite.prisma', 'sql', 'people', ('email',), ()),
            ('prisma/migrations/', 'prisma/schema.prisma', 'sql-table', 'logs', ('<table>',), ()),
            ('prisma/rebuild.sql', 'prisma/schema.prisma', 'sql', 'items', ('name',), ()),
        ], found


def test_label_groups_keep_codes_routes_and_test_spellings_apart(tmp_path):
    # Planning Tool 0.6.28 listed 207 old label leads and none was a label spelled two ways: an enum code next to
    # a key ('ACTIVE' / 'Active'), a route next to a key ('/admin' / 'admin'), or spellings only tests use.
    with closing(project(tmp_path, {
        'src/units.ts': '''export function label(type: string) {
  if (type === 'MAIN_DEPARTMENT') { return 'Main Department'; }
  if (type === 'main-department') { return 'Main department'; }
  if (type === '/admin') { return 'admin'; }
  return type === 'ACTIVE' ? 'Active' : 'active';
}
''',
        'tests/units.test.ts': '''export function expectLabel(found: string) {
  return found === 'My organization' || found === 'Admin';
}
''',
        'src/nav.ts': "export const title = (mine: boolean) => mine ? 'My Organization' : 'Other';\n",
    })) as graph:
        groups = sorted((group['key'], sorted(group['spellings'])) for group in graph.literal_groups())
        assert groups == [('active', ['Active', 'active']), ('maindepartment', ['Main Department', 'Main department'])], groups
