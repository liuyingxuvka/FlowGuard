"""Prisma schema and SQL text readers, and string-literal facts that must stay quiet."""
from contextlib import closing

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
    })) as graph:
        writes = [(row['model'], row['field'], row['kind']) for row in graph.writes()]
        assert writes == [('Item', 'name', 'update'), ('Item', 'id', 'sql:insert'), ('Item', 'name', 'sql:insert')]
        values = sorted((row['value'], row['context']) for row in graph.literals(language='javascript'))
        assert values == [('Ok', 'return'), ('id', 'compare'), ('ok', 'return')]
        groups = graph.literal_groups()
        assert [group['key'] for group in groups] == ['ok']          # 'id' / 'ID' as keys never group
