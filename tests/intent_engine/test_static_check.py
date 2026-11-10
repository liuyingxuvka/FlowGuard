"""`check --static` and the structure health checks (round 20, stage 7b and 5b; fixed examples 16 and 17).

Each project commits its baseline first; only what the working tree adds is reported, and `--all` also
lists every open structure problem. The Planning Tool fragments come from `tests/fixtures/planning_tool`
and `tests/fixtures/planning_tool_static` (sources and line ranges in their READMEs).
"""
from contextlib import closing
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import textwrap

import pytest

from tests.intent_engine import _cli_fixture
from tests.intent_engine._cli_fixture import display_text as _text

from flowguard.intent import anchors
from flowguard.structure import build

SOURCE = str(Path(__file__).resolve().parents[2])
FIXTURES = Path(__file__).resolve().parents[1] / 'fixtures'
STUB_VITEST = "export function test(name, body) { globalThis.__flowguard_tests.push([name, body]); }\n"
RUN_STUB = '''
globalThis.__flowguard_tests = [];
const target = process.argv[2];
await import(new URL('file://' + target).href);
let failed = 0;
for (const [name, body] of globalThis.__flowguard_tests) {
  try { await body(); console.log('PASS ' + name); }
  catch (error) { failed += 1; console.log('FAIL ' + name + ': ' + error.message); }
}
process.exit(failed ? 1 : 0);
'''


def _git(root, *arguments):
    return subprocess.run(['git', '-C', str(root), *arguments], check=True, capture_output=True, text=True, timeout=20).stdout


def _write(root, files):
    for name, text in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(textwrap.dedent(text).lstrip() if not name.endswith('.toml') else text, encoding='utf-8')


def _commit(root, files=(), message='fixture baseline'):
    _write(root, {'.gitignore': '.flowguard/cache/\n__pycache__/\n.pytest_cache/\nnode_modules/\n', **dict(files)})
    if not (root / '.git').exists():
        _git(root, 'init', '-q', '-b', 'main')
    _git(root, 'add', '.')
    _git(root, '-c', 'user.name=Test', '-c', 'user.email=test@example.invalid', 'commit', '-qm', message)
    return root


def _planning(root, *folders):
    for folder in ('planning_tool', *folders):
        for path in (FIXTURES / folder).rglob('*.txt'):
            target = root / path.relative_to(FIXTURES / folder).with_suffix('')
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(path.read_bytes())
    return root


def _flowguard(root, *arguments, env=None):
    result = subprocess.run([sys.executable, '-c', _cli_fixture._BOOT, SOURCE, 'unused-marker', '', '--root', str(root), *arguments],
                            cwd=root, capture_output=True, encoding='utf-8', timeout=180,
                            # The boot calls cli.main without the entry's safe stdio: a cp1252 console needs utf-8.
                            env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1', PYTHONIOENCODING='utf-8', **(env or {})))
    return result.returncode, _text(result)


def _static(root, *options):
    return _flowguard(root, 'check', '--static', *options)


def _lines(text, prefix):
    return [line for line in text.splitlines() if line.startswith(prefix)]


# ---- check --static: only what the change adds; exit 1 on red --------------------------------------

def test_check_static_reports_only_new_values_outside_a_check_and_lists_old_ones_with_all(tmp_path):
    _commit(_planning(tmp_path, 'planning_tool_static'))
    code, text = _static(tmp_path)
    assert (code, text) == (0, ''), text                      # nothing changed: not one line
    code, text = _static(tmp_path, '--all')
    assert code == 0, text
    old = next(line for line in text.splitlines() if line.startswith('1. 取值：'))
    assert old == ("1. 取值：取值不在声明集合里：backend/src/services/authority/authority-integrity-repair.service.ts:20 "
                   "AuditEvent.severity='WARN'，允许 INFO|WARNING|ERROR|CRITICAL（CHECK backend/prisma/migrations/"
                   "20260910120000_align_runtime_storage_contract/migration.sql:9）"), old
    _write(tmp_path, {'backend/src/services/notice.service.ts': '''
        export async function notice(prisma: any, id: string) {
          await prisma.auditEvent.create({ data: { severity: 'WARNING', entityId: id } });
          await prisma.auditEvent.create({ data: { severity: id ? 'NOTICE' : 'INFO', entityId: id } });
        }
    '''})
    code, text = _static(tmp_path)
    assert code == 1, text
    red = _lines(text, '红：')
    assert red == ["红：取值不在声明集合里：backend/src/services/notice.service.ts:3 AuditEvent.severity='NOTICE'，允许 "
                   "INFO|WARNING|ERROR|CRITICAL（CHECK backend/prisma/migrations/20260910120000_align_runtime_storage_contract/"
                   "migration.sql:9） → 改用集合里的值；集合真要加值，先改那条声明（CHECK backend/prisma/migrations/"
                   "20260910120000_align_runtime_storage_contract/migration.sql:9）"], text
    code, text = _flowguard(tmp_path, 'check', '--static', '--deep')
    assert code == 2 and 'check --static runs no tests' in text, text


def test_the_title_of_check_static_base_names_the_cli_option(tmp_path):
    _commit(_planning(tmp_path, 'planning_tool_static'))
    head = _git(tmp_path, 'rev-parse', 'HEAD').strip()
    _write(tmp_path, {'backend/src/services/notice.service.ts': '''
        export async function notice(prisma: any, id: string) {
          await prisma.auditEvent.create({ data: { severity: 'NOTICE', entityId: id } });
        }
    '''})
    code, text = _static(tmp_path, '--base', 'HEAD')
    assert code == 1 and text.splitlines()[0] == 'FlowGuard（相对 --base HEAD）', text      # the option the CLI took
    code, text = _static(tmp_path)
    assert code == 1 and text.splitlines()[0] == f'FlowGuard（相对任务开始 {head[:7]}）', text


def test_value_sets_come_from_prisma_enums_sql_checks_and_typescript_types(tmp_path):
    _write(tmp_path, {
        'prisma/schema.prisma': '''
            datasource db {
              provider = "postgresql"
              url      = env("DATABASE_URL")
            }

            enum Role {
              ADMIN
              MEMBER
            }

            model Account {
              id     String @id
              role   Role
              status String
              kind   String @map("account_kind")
              @@map("accounts")
            }
        ''',
        'prisma/migrations/001/migration.sql': '''
            CREATE TABLE accounts (id TEXT, status TEXT CHECK (status IN ('open', 'closed')), account_kind TEXT);
            EXEC(N'ALTER TABLE [dbo].[accounts] ADD CONSTRAINT [CK_kind] CHECK ([account_kind] IN (N''USER'', N''BOT''))');
            ALTER TABLE accounts ADD CONSTRAINT ck_ranged CHECK (id > 0);
        ''',
        'src/types.ts': '''
            export const STATES = ['DRAFT', 'LIVE'] as const;
            export type State = (typeof STATES)[number];
            export const Kind = { USER: 'USER', BOT: 'BOT' } as const;
            interface Event { severity: 'low' | 'high'; state?: State; }
            class Job {
              state: State = 'DRAFT';
              go() { this.state = 'GONE'; }
            }
            const first: Event = { severity: 'mid' };
            const second = { severity: 'low', state: 'LIVE' } satisfies Event;
        ''',
        'src/accounts.ts': '''
            import { Kind } from './types';
            export async function open(prisma: any, flag: boolean) {
              await prisma.account.create({ data: { role: 'OWNER', status: flag ? 'open' : 'archived', kind: Kind.BOT } });
              await prisma.account.update({ where: { id: '1' }, data: { kind: Kind.ROBOT, status: null } });
            }
        ''',
    })
    with closing(build(tmp_path)) as graph:
        sets = {row['key']: (row['values'], row['kind']) for row in graph.value_sets()}
        assert sets == {'Account.role': (('ADMIN', 'MEMBER'), 'prisma-enum'), 'Account.status': (('open', 'closed'), 'sql-check'),
                        'Account.kind': (('USER', 'BOT'), 'sql-check'), 'Event.severity': (('low', 'high'), 'ts-type'),
                        'Event.state': (('DRAFT', 'LIVE'), 'ts-type'), 'Job.state': (('DRAFT', 'LIVE'), 'ts-type')}, sets
        from flowguard.intent import health, owners
        change = owners.Change(_config(tmp_path), graph, None)
        table = anchors.declared_sets((), foreign=graph.value_sets())
        outside = sorted((row['file'], row['line'], row['field'], value)
                         for row, _, value in anchors.outside_sets(table, health._foreign_writes(change)))
    assert outside == [('src/accounts.ts', 3, 'Account.role', 'OWNER'), ('src/accounts.ts', 3, 'Account.status', 'archived'),
                       ('src/types.ts', 7, 'Job.state', 'GONE'), ('src/types.ts', 9, 'Event.severity', 'mid')], outside
    # Kind.BOT resolves through the `as const` object; Kind.ROBOT names no member, so its value is not judged.


def test_a_package_whose_prisma_files_name_no_schema_in_use_is_judged_by_all_of_them_and_says_so(tmp_path):
    # Round 21 verification of V1: with only provider templates committed (the generated schema.prisma is
    # git-ignored) or one schema under another name, every Prisma enum stopped gating without a word.
    schema = """
        enum Kind {
          A
          B
        }

        model Item {
          id   String @id
          kind Kind
        }
    """
    write = {'src/items.ts': """
        export async function add(prisma: any, id: string) {
          await prisma.item.create({ data: { id, kind: 'C' } });
        }
    """}
    for files in ({'prisma/schema.sqlite.prisma': schema, 'prisma/schema.postgres.prisma': schema},
                  {'prisma/main.prisma': schema}):
        root = tmp_path / str(len(files))
        _commit(root, files)
        _write(root, write)
        code, text = _static(root)
        red = _lines(text, '红：取值')
        assert code == 1 and len(red) == 1 and "src/items.ts:2 Item.kind='C'，允许 A|B" in red[0], text
        assert '没找到生成器在用的 schema，按这个包的全部 schema 判' in red[0], red
        # the files that spell the enum alike share one set, which names each of them
        assert '（enum Kind (' + ', '.join(f'{file}:1' for file in sorted(files)) + '，没找到' in red[0], red
    # prisma.config.ts names the schema in use: the template beside it only describes, and nothing is guessed
    root = tmp_path / 'config'
    _commit(root, {'prisma/schema.sqlite.prisma': schema.replace('  B\n', '  B\n          C\n'),
                   'prisma/schema.postgres.prisma': schema,
                   'prisma.config.ts': "import { defineConfig } from 'prisma/config';\n"
                                       "export default defineConfig({ schema: 'prisma/schema.postgres.prisma' });\n"})
    _write(root, write)
    code, text = _static(root)
    red = _lines(text, '红：取值')
    assert code == 1 and len(red) == 1 and '（enum Kind (prisma/schema.postgres.prisma:1)）' in red[0], text


def test_a_guessed_schema_fills_only_models_no_schema_in_use_defines_and_each_of_its_enums_is_a_set(tmp_path):
    # 4.2 review: the guessed templates of one package gated another package's writes to the models of its own
    # schema in use (a false red), and of two guessed templates only the first by path judged, although the
    # line says all of them do.
    def schema(kinds, tones=None):
        text = 'enum Kind {\n' + ''.join(f'  {name}\n' for name in kinds) + '}\n\nmodel Item {\n  id   String @id\n  kind Kind\n}\n'
        if tones:
            text += '\nenum Tone {\n' + ''.join(f'  {name}\n' for name in tones) + '}\n\nmodel Note {\n  id   String @id\n  tone Tone\n}\n'
        return text
    _commit(tmp_path, {
        'admin/package.json': '{"name": "admin"}\n',
        'admin/prisma/schema.postgres.prisma': schema('AB', 'XY'),
        'admin/prisma/schema.sqlite.prisma': schema('AD', 'X'),
        'server/package.json': '{"name": "server"}\n',
        'server/prisma/schema.prisma': schema('ABC'),
    })
    items = """
        export async function add(prisma: any, id: string) {
          await prisma.item.create({ data: { id, kind: 'C' } });
        }
    """
    _write(tmp_path, {'server/src/items.ts': items, 'admin/src/items.ts': items, 'admin/src/notes.ts': """
        export async function note(prisma: any, id: string) {
          await prisma.note.create({ data: { id, tone: 'Y' } });
          await prisma.note.create({ data: { id, tone: 'Z' } });
        }
    """})
    with closing(build(tmp_path)) as graph:
        sets = [(row['field'], row['values'], row['file']) for row in graph.value_sets()]
        from flowguard.intent import health, owners
        names = sorted(issue.name for issue in health.values(owners.Change(_config(tmp_path), graph, None)).issues)
    # Item is the server schema's model: the admin templates do not gate it, in either package
    assert sets == [('Item.kind', ('A', 'B', 'C'), 'server/prisma/schema.prisma'),
                    ('Note.tone', ('X', 'Y'), 'admin/prisma/schema.postgres.prisma'),
                    ('Note.tone', ('X',), 'admin/prisma/schema.sqlite.prisma')], sets
    # 4.1 named the field's one problem values:Note.tone: the first guessed set keeps that name (r25, docs-0)
    assert names == ['values:Note.tone', 'values:Note.tone:admin/prisma/schema.sqlite.prisma'], names
    code, text = _static(tmp_path)
    guessed = '，没找到生成器在用的 schema，按这个包的全部 schema 判'
    postgres, sqlite = (f'enum Tone (admin/prisma/schema.{name}.prisma:11{guessed})' for name in ('postgres', 'sqlite'))
    assert code == 1 and _lines(text, '红：取值') == [
        f"红：取值不在声明集合里：admin/src/notes.ts:3 Note.tone='Z'，允许 X|Y（{postgres}） → 改用集合里的值；集合真要加值，"
        f"先改那条声明（{postgres}）；admin/src/notes.ts:2 Note.tone='Y'  admin/src/notes.ts:3 Note.tone='Z'，允许 X（{sqlite}）"
        f" → 改用集合里的值；集合真要加值，先改那条声明（{sqlite}）"], text
    # A further set keeps its name when it is the only one broken and when its lines move.
    _write(tmp_path, {'admin/src/notes.ts': """
        export async function note(prisma: any, id: string) {
          await prisma.note.create({ data: { id, tone: 'Y' } });
        }
    """, 'admin/prisma/schema.sqlite.prisma': '// moved\n\n' + schema('AD', 'X')})
    with closing(build(tmp_path)) as graph:
        names = [issue.name for issue in health.values(owners.Change(_config(tmp_path), graph, None)).issues]
    assert names == ['values:Note.tone:admin/prisma/schema.sqlite.prisma'], names


def test_archived_prisma_files_are_neither_in_use_nor_guessed(tmp_path):
    # 4.2 review: a release snapshot under docs/ took part in the schemas in use and in the guess; one named
    # schema.prisma even made its package look decided, so the live file stopped gating and the snapshot gated.
    def schema(*kinds):
        return 'enum Kind {\n' + ''.join(f'  {name}\n' for name in kinds) + '}\n\nmodel Item {\n  id   String @id\n  kind Kind\n}\n'
    _commit(tmp_path, {'prisma/main.prisma': schema('A', 'B'), 'docs/release-1.0/schema.prisma': schema('A', 'B', 'C'),
                       'docs/history/old.prisma': schema('A', 'B', 'C', 'D')})
    _write(tmp_path, {'src/items.ts': """
        export async function add(prisma: any, id: string) {
          await prisma.item.create({ data: { id, kind: 'C' } });
        }
    """})
    with closing(build(tmp_path)) as graph:
        assert graph.prisma_schemas_in_use() == graph.prisma_schemas_guessed() == {'prisma/main.prisma'}
        assert [(row['field'], row['values'], row['file']) for row in graph.value_sets()] == \
            [('Item.kind', ('A', 'B'), 'prisma/main.prisma')], graph.value_sets()
    code, text = _static(tmp_path)
    assert code == 1 and _lines(text, '红：取值') == [
        "红：取值不在声明集合里：src/items.ts:2 Item.kind='C'，允许 A|B（enum Kind (prisma/main.prisma:1，没找到生成器在用的 schema，"
        "按这个包的全部 schema 判)） → 改用集合里的值；集合真要加值，先改那条声明（enum Kind (prisma/main.prisma:1，没找到生成器在用的 "
        "schema，按这个包的全部 schema 判)）"], text
    # `archives = []` makes every file live: the snapshot named schema.prisma is then the schema in use
    _write(tmp_path, {'pyproject.toml': '[tool.flowguard]\narchives = []\n'})
    with closing(build(tmp_path)) as graph:
        assert graph.prisma_schemas_in_use() == {'docs/release-1.0/schema.prisma'} and not graph.prisma_schemas_guessed()


def _tone_schema(*tones):
    return 'enum Tone {\n' + ''.join(f'  {name}\n' for name in tones) + '}\n\nmodel Note {\n  id   String @id\n  tone Tone\n}\n'


def _tone_writes(*tones):
    return ('export async function note(prisma: any, id: string) {\n'
            + ''.join(f"  await prisma.note.create({{ data: {{ id, tone: '{tone}' }} }});\n" for tone in tones) + '}\n')


def test_a_guessed_schema_judges_the_writes_of_its_own_package_and_of_a_package_without_prisma_files(tmp_path):
    # 4.2 review: two packages whose templates are both guessed judged each other's writes (a false red in
    # both directions), while the red says it judges by this package's schemas.
    _commit(tmp_path, {
        'admin/package.json': '{"name": "admin"}\n',
        'admin/prisma/schema.postgres.prisma': _tone_schema('X', 'Y'),
        'web/package.json': '{"name": "web"}\n',
        'web/prisma/schema.sqlite.prisma': _tone_schema('X', 'Z'),
    })
    _write(tmp_path, {'admin/src/a.ts': _tone_writes('Y', 'Z'), 'web/src/b.ts': _tone_writes('Z'),
                      # the root package has no Prisma file of its own: each guessed set judges it
                      'scripts/seed.ts': _tone_writes('W')})
    with closing(build(tmp_path)) as graph:
        from flowguard.intent import health, owners
        names = sorted(issue.name for issue in health.values(owners.Change(_config(tmp_path), graph, None)).issues)
    assert names == ['values:Note.tone', 'values:Note.tone:web/prisma/schema.sqlite.prisma'], names
    code, text = _static(tmp_path)
    guessed = '，没找到生成器在用的 schema，按这个包的全部 schema 判'
    admin, web = f'enum Tone (admin/prisma/schema.postgres.prisma:1{guessed})', f'enum Tone (web/prisma/schema.sqlite.prisma:1{guessed})'
    assert code == 1 and _lines(text, '红：取值') == [
        f"红：取值不在声明集合里：admin/src/a.ts:3 Note.tone='Z'  scripts/seed.ts:2 Note.tone='W'，允许 X|Y（{admin}） → "
        f"改用集合里的值；集合真要加值，先改那条声明（{admin}）；scripts/seed.ts:2 Note.tone='W'，允许 X|Z（{web}） → "
        f"改用集合里的值；集合真要加值，先改那条声明（{web}）"], text


def test_guessed_templates_with_the_same_enum_share_one_set_that_names_every_file(tmp_path):
    # 4.2 review: three provider templates with one enum repeated the same red segment and the same problem
    # three times, so `--all` and the brief counted it three times.
    _commit(tmp_path, {'prisma/schema.sqlite.prisma': _tone_schema('X', 'Y'), 'prisma/schema.postgres.prisma': _tone_schema('X', 'Y'),
                       'prisma/schema.sqlserver.prisma': _tone_schema('X', 'Y'), 'prisma/schema.mysql.prisma': _tone_schema('X')})
    _write(tmp_path, {'src/notes.ts': _tone_writes('Y', 'Z')})
    code, text = _static(tmp_path)
    guessed = '，没找到生成器在用的 schema，按这个包的全部 schema 判'
    one = f'enum Tone (prisma/schema.mysql.prisma:1{guessed})'
    three = f'enum Tone (prisma/schema.postgres.prisma:1, prisma/schema.sqlite.prisma:1, prisma/schema.sqlserver.prisma:1{guessed})'
    assert code == 1 and _lines(text, '红：取值') == [
        f"红：取值不在声明集合里：src/notes.ts:2 Note.tone='Y'  src/notes.ts:3 Note.tone='Z'，允许 X（{one}） → 改用集合里的值；"
        f"集合真要加值，先改那条声明（{one}）；src/notes.ts:3 Note.tone='Z'，允许 X|Y（{three}） → 改用集合里的值；"
        f"集合真要加值，先改那条声明（{three}）"], text
    with closing(build(tmp_path)) as graph:
        sets = [(row['values'], row['files']) for row in graph.value_sets()]
        from flowguard.intent import health, owners
        names = [issue.name for issue in health.values(owners.Change(_config(tmp_path), graph, None)).issues]
    assert sets == [(('X',), ('prisma/schema.mysql.prisma',)),
                    (('X', 'Y'), ('prisma/schema.postgres.prisma', 'prisma/schema.sqlite.prisma', 'prisma/schema.sqlserver.prisma'))], sets
    assert names == ['values:Note.tone', 'values:Note.tone:prisma/schema.postgres.prisma'], names


def test_a_value_set_problem_takes_the_name_4_1_gave_its_field_and_a_further_set_adds_its_place(tmp_path):
    # 4.2 review: a field's plain problem name went to whichever of its sets sorted first, so a decision
    # recorded on a TS type's or a CHECK's problem moved to a Prisma enum added later. r24 review (gate-6,
    # gate-7, docs-0): 4.1 named the one value problem of every field `values:Model.field`, so a 4.1 decision on
    # a CHECK-only or TS-only field stopped matching once those sets added their file, and a later migration
    # that declares the same CHECK again renamed the problem. The plain name goes to the set 4.1 named so: the
    # enum of a schema in use, else the CHECK, else the TS type, else a guessed enum; each further set adds its
    # place, a CHECK its description (the migrations folder).
    schema = ('model Note {\n  id   String @id\n  tone String\n}\n\n'
              'model Account {\n  id     String @id\n  status String\n  @@map("accounts")\n}\n')
    _commit(tmp_path, {
        'prisma/schema.prisma': schema,
        'prisma/migrations/001/migration.sql': "CREATE TABLE accounts (id TEXT, status TEXT CHECK (status IN ('open', 'closed')));\n",
        'web/types.ts': "export interface Note { tone: 'X' | 'W'; }\n",
        'web/n.ts': "import type { Note } from './types';\nexport const n: Note = { tone: 'V' };\n",
        'src/a.ts': """
            export async function add(prisma: any, id: string) {
              await prisma.note.create({ data: { id, tone: 'Z' } });
              await prisma.account.create({ data: { id, status: 'gone' } });
            }
        """,
    })

    def names():
        from flowguard.intent import health, owners
        with closing(build(tmp_path)) as graph:
            return sorted(issue.name for issue in health.values(owners.Change(_config(tmp_path), graph, None)).issues)
    assert names() == ['values:Account.status', 'values:Note.tone'], names()
    # 002 drops and adds the same CHECK again (as altering the column needs): the problem keeps its name
    _write(tmp_path, {'prisma/migrations/002/migration.sql': "ALTER TABLE accounts DROP CONSTRAINT ck_status;\n"
                                                           "ALTER TABLE accounts ADD CONSTRAINT ck_status CHECK (status IN ('open', 'closed'));\n"})
    _commit(tmp_path, message='declare the CHECK again')
    assert names() == ['values:Account.status', 'values:Note.tone'], names()
    code, text = _static(tmp_path, '--all')
    assert code == 0 and "Account.status='gone'，允许 open|closed（CHECK prisma/migrations/002/migration.sql:2）" in text, text
    # the decision a 4.1 project recorded on that field still closes it
    sentence = 'Old accounts keep the status gone until the cleanup job removes them.'
    _write(tmp_path, {'docs/decisions.md': sentence + '\n', '.flowguard/ledger.toml': (
        '[structure."values:Account.status"]\ndecision = "old accounts keep the status gone until the cleanup job removes them"\n'
        f'source = {{ file = "docs/decisions.md", text = "{sentence}" }}\n')})
    code, text = _static(tmp_path, '--all')
    assert code == 0 and 'Account.status' not in text and "Note.tone='V'" in text, text
    # an enum of the schema in use takes the plain name; the CHECK and the TS type add their place
    _write(tmp_path, {'prisma/schema.prisma': 'enum Tone {\n  X\n  Y\n}\n\nenum Status {\n  open\n  closed\n}\n\n'
                                              + schema.replace('tone String', 'tone Tone').replace('status String', 'status Status')})
    assert names() == ['values:Account.status', 'values:Account.status:prisma/migrations/', 'values:Note.tone',
                       'values:Note.tone:web/types.ts'], names()


def test_a_generator_output_under_node_modules_is_the_client_by_its_package_name(tmp_path):
    # 4.2 review: Prisma's setup for several databases writes each client into node_modules and imports it by
    # its package name; only a relative import of that folder counted as the client. The Planning Tool
    # imports `.prisma/central-client` so.
    def schema(output, enum, model, values):
        return (f'generator client {{\n  provider = "prisma-client-js"\n  output   = "{output}"\n}}\n\nenum {enum} {{\n'
                + ''.join(f'  {value}\n' for value in values) + f'}}\n\nmodel {model} {{\n  id   String @id\n  role {enum}\n}}\n')
    _commit(tmp_path, {
        'backend/package.json': '{"name": "backend"}\n',
        'backend/prisma/schema.prisma': schema('../node_modules/@prisma-db-1/client', 'Role', 'User', 'AB'),
        'backend/prisma/central/schema.prisma': schema('../../node_modules/.prisma/central-client', 'Tier', 'Person', 'XY'),
        'web/package.json': '{"name": "web"}\n',
    })
    _write(tmp_path, {
        'backend/src/a.ts': "import type { User } from '@prisma-db-1/client';\nexport const a: User = { id: '1', role: 'N1' };\n",
        'backend/src/b.ts': "import type { Prisma as CentralPrisma } from '.prisma/central-client';\n"
                            "export const b: CentralPrisma.Person = { id: '2', role: 'N2' };\n",
        'backend/src/c.ts': "import type { User } from '../node_modules/@prisma-db-1/client';\n"
                            "export const c: User = { id: '3', role: 'N3' };\n",
        # outside backend/ the package name resolves to another node_modules folder: not this client
        'web/src/d.ts': "import type { User } from '@prisma-db-1/client';\nexport const d: User = { id: '4', role: 'N4' };\n",
    })
    code, text = _static(tmp_path)
    role, tier = 'enum Role (backend/prisma/schema.prisma:6)', 'enum Tier (backend/prisma/central/schema.prisma:6)'
    assert code == 1 and _lines(text, '红：取值') == [
        f"红：取值不在声明集合里：backend/src/b.ts:2 Person.role='N2'，允许 X|Y（{tier}） → 改用集合里的值；集合真要加值，"
        f"先改那条声明（{tier}）；backend/src/a.ts:2 User.role='N1'  backend/src/c.ts:2 User.role='N3'，允许 A|B（{role}） → "
        f"改用集合里的值；集合真要加值，先改那条声明（{role}）"], text


def test_a_package_json_that_is_not_json_names_its_file(tmp_path):
    _commit(tmp_path, {'web/package.json': '{"name": "web",\n', 'web/prisma/main.prisma': 'model Item {\n  id String @id\n}\n'})
    code, text = _static(tmp_path)
    assert code == 2 and 'web/package.json is not valid JSON' in text, text


def test_an_object_typed_with_a_prisma_client_type_is_gated_by_its_model(tmp_path):
    # Round 21 verification of V2: keeping TS types apart from Prisma models also stopped gating an object
    # typed with the model's own generated type.
    _commit(tmp_path, {'prisma/schema.prisma': """
        enum Kind {
          A
          B
        }

        model Item {
          id   String @id
          kind Kind
        }
    """})
    _write(tmp_path, {
        'src/sample.ts': """
            import type { Item } from '@prisma/client';
            export const sample: Item = { id: '1', kind: 'C' };
        """,
        'src/own.ts': """
            interface Item { id: string; kind: string }
            export const mine: Item = { id: '1', kind: 'C' };
        """,
    })
    code, text = _static(tmp_path)
    red = _lines(text, '红：取值')
    assert code == 1 and len(red) == 1 and red[0].startswith("红：取值不在声明集合里：src/sample.ts:2 Item.kind='C'，允许 A|B"), text


def test_a_type_from_one_schemas_client_output_is_judged_by_that_schema_and_a_guess_reaches_packages_without_its_model(tmp_path):
    # Round 23 check of r23-gate: with two schemas in use declaring User.role differently, a typed object imported
    # from the second schema's client output was judged by the first; and a guessed schema stopped judging a
    # package that has a Prisma file of its own but does not define the guessed model.
    def schema(output, values):
        return (f'generator client {{\n  provider = "prisma-client-js"\n  output   = "{output}"\n}}\n\n'
                f'enum Role {{\n' + ''.join(f'  {value}\n' for value in values) + '}\n\n'
                'model User {\n  id   String @id\n  role Role\n}\n')
    root = tmp_path / 'outputs'
    _commit(root, {
        'backend/package.json': '{"name": "backend"}',
        'backend/prisma/db1/schema.prisma': schema('../../node_modules/@prisma-db-1/client', 'AB'),
        'backend/prisma/db2/schema.prisma': schema('../../node_modules/@prisma-db-2/client', 'AC'),
    })
    _write(root, {'backend/src/a.ts': """
        import type { User } from '@prisma-db-2/client';
        import type { User as Other } from '@prisma-db-1/client';
        export const a: User = { id: '1', role: 'C' };
        export const b: User = { id: '2', role: 'B' };
        export const c: Other = { id: '3', role: 'C' };
    """})
    code, text = _static(root)
    red = '\n'.join(_lines(text, '红：取值'))
    assert code == 1, text
    assert "backend/src/a.ts:4 User.role='B'，允许 A|C（enum Role (backend/prisma/db2/schema.prisma:6)）" in red, red
    assert "backend/src/a.ts:5 User.role='C'，允许 A|B（enum Role (backend/prisma/db1/schema.prisma:6)）" in red, red
    assert 'a.ts:3' not in red, red                 # 'C' is db2's own value
    root = tmp_path / 'guess'
    note = 'enum Tone {\n  X\n  Y\n}\n\nmodel Note {\n  id   String @id\n  tone Tone\n}\n'
    _commit(root, {
        'db/package.json': '{"name": "db"}', 'db/prisma/schema.postgres.prisma': note,
        'api/package.json': '{"name": "api"}', 'api/prisma/schema.prisma': 'model Extra {\n  id String @id\n}\n',
        'web/package.json': '{"name": "web"}', 'web/prisma/schema.prisma': note.replace('  Y\n', '  Z\n'),
    })
    _write(root, {
        'api/src/a.ts': "export async function add(prisma: any, id: string) {\n  await prisma.note.create({ data: { id, tone: 'Q' } });\n}\n",
        'web/src/n.ts': "export async function add(prisma: any, id: string) {\n  await prisma.note.create({ data: { id, tone: 'Z' } });\n}\n",
    })
    code, text = _static(root)
    red = [line.partition(' → ')[0] for line in _lines(text, '红：取值')]
    # api defines no Note: db's guessed template still judges it; web defines Note itself and is not judged by db
    assert code == 1 and len(red) == 1 and "api/src/a.ts:2 Note.tone='Q'" in red[0] and 'web/src' not in red[0], text


def _role_schema(values, output=None, source=None):
    """A schema of `User.role`, typed by `enum Role` of these values, or `String` when `values` is None."""
    return ((f'datasource db {{\n  provider = "{source}"\n  url      = env("DATABASE_URL")\n}}\n\n' if source else '')
            + (f'generator client {{\n  provider = "prisma-client-js"\n  output   = "{output}"\n}}\n\n' if output else '')
            + ('model User {\n  id   String @id\n  role String\n}\n' if values is None else
               'enum Role {\n' + ''.join(f'  {value}\n' for value in values) + '}\n\nmodel User {\n  id   String @id\n  role Role\n}\n'))


def _red_values(text):
    """Each set's part of the value red line, `places，允许 values（where）`, without the step after it."""
    head, step, out = '红：取值不在声明集合里：', ' → 改用集合里的值；集合真要加值，先改那条声明（', []
    for line in _lines(text, head):
        rest = line[len(head):]
        while rest:
            part, _, rest = rest.partition(step)
            out.append(part)
            rest = rest.partition('）')[2].removeprefix('；')
    return out


def test_a_schema_that_lacks_the_field_or_a_template_that_types_it_as_text_keeps_the_enum_judging(tmp_path):
    # Final check of r25-gate: a second schema in use of the package whose model lacks the field (a reporting
    # client) or types it as String (a SQLite template pushed with --schema) turned the enum gate off.
    write = ("import type { User } from '@prisma/client';\n"
             "export async function add(prisma: any, id: string) {\n  await prisma.user.create({ data: { id, role: 'Z' } });\n}\n"
             "export const u: User = { id: '1', role: 'Z' };\n")
    for name, files in (
            ('reporting', {'package.json': '{"name": "app", "scripts": {"gen": "prisma generate --schema prisma/reporting.prisma"}}',
                           'prisma/schema.prisma': _role_schema('AB'),
                           'prisma/reporting.prisma': 'generator reporting {\n  provider = "prisma-client-js"\n  output   = '
                                                      '"../src/generated/reporting"\n}\n\nmodel User {\n  id   String @id\n  name String\n}\n'}),
            ('template', {'package.json': '{"name": "app", "scripts": {"dev": "prisma db push --schema prisma/schema.sqlite.prisma"}}',
                          'prisma/schema.prisma': _role_schema('AB', source='postgresql'),
                          'prisma/schema.sqlite.prisma': _role_schema(None, source='sqlite')})):
        root = tmp_path / name
        _commit(root, files)
        _write(root, {'src/w.ts': write})
        code, text = _static(root)
        assert code == 1 and _red_values(text) == [
            "src/w.ts:3 User.role='Z'  src/w.ts:5 User.role='Z'，允许 A|B（enum Role (prisma/schema.prisma:%d)）"
            % (1 if name == 'reporting' else 6)], (name, text)


def test_a_member_typed_with_an_imported_alias_is_judged_by_the_alias_the_file_imports(tmp_path):
    # Final check of r25-gate, seen on Planning Tool: Granularity is declared in several files, one test file with
    # other values, so an interface member typed with the imported Granularity resolved to no set and its objects
    # went unjudged.
    _commit(tmp_path, {
        'src/types/units.ts': "export type Granularity = 'WEEK' | 'MONTH';\n",
        'src/other/units.ts': "export type Granularity = 'WEEK' | 'MONTH';\n",
        'tests/units.test.ts': "export type Granularity = 'DAY' | 'WEEK' | 'MONTH';\n",
        'src/types/grid.ts': "import type { Granularity } from './units';\nexport interface Grid { granularity: Granularity }\n",
    })
    _write(tmp_path, {'src/page.ts': "import type { Grid } from './types/grid';\nexport const g: Grid = { granularity: 'MONTHLY' };\n"})
    code, text = _static(tmp_path)
    red = _red_values(text)
    assert code == 1 and len(red) == 1 and red[0].startswith("src/page.ts:2 Grid.granularity='MONTHLY'，允许 WEEK|MONTH"), text


def test_a_schema_folder_is_one_schema_for_its_enums_and_its_datasource(tmp_path):
    # r24 review (gate-3): a schema folder was read file by file, so an enum another file declares gated
    # nothing (a false green) and the folder's SQL Server datasource did not make a CHECK compare without case.
    folder = {
        'prisma/schema/schema.prisma': 'datasource db {\n  provider = "sqlserver"\n  url      = env("DATABASE_URL")\n}\n',
        'prisma/schema/enums.prisma': 'enum Role {\n  A\n  B\n}\n',
        'prisma/schema/user.prisma': 'model User {\n  id   String @id\n  role Role\n}\n',
        'prisma/schema/account.prisma': 'model Account {\n  id     String @id\n  status String\n  @@map("accounts")\n}\n',
        'prisma/migrations/001/migration.sql': "CREATE TABLE accounts (id NVARCHAR(36), status NVARCHAR(10) CHECK (status IN ('open', 'closed')));\n",
    }
    writes = {'src/a.ts': """
        export async function add(prisma: any, id: string) {
          await prisma.user.create({ data: { id, role: 'C' } });
          await prisma.account.create({ data: { id, status: 'OPEN' } });
          await prisma.account.create({ data: { id, status: 'gone' } });
        }
    """}
    for name, files in (('named', {'package.json': '{"name": "app", "prisma": {"schema": "prisma/schema"}}\n', **folder}),
                        ('default', folder)):
        root = tmp_path / name
        _commit(root, files)
        _write(root, writes)
        code, text = _static(root)
        # 'OPEN' passes: SQL Server compares without case
        assert code == 1 and _red_values(text) == [
            "src/a.ts:4 Account.status='gone'，允许 open|closed（CHECK prisma/migrations/001/migration.sql:1）",
            "src/a.ts:2 User.role='C'，允许 A|B（enum Role (prisma/schema/enums.prisma:1)）"], (name, text)


def test_a_prisma_write_is_judged_by_the_schema_in_use_of_its_own_package(tmp_path):
    # r24 review (gate-5): two services, each with its own schema.prisma, and one service's writes were judged
    # by the other's enum, the first schema in use by path.
    _commit(tmp_path, {
        'apps/api/package.json': '{"name": "api"}', 'apps/api/prisma/schema.prisma': _role_schema('AB'),
        'apps/worker/package.json': '{"name": "worker"}', 'apps/worker/prisma/schema.prisma': _role_schema('AC'),
    })
    write = "export async function add(prisma: any, id: string) {\n  await prisma.user.create({ data: { id, role: '%s' } });\n}\n"
    _write(tmp_path, {
        'apps/worker/src/w.ts': write % 'C',
        'apps/worker/src/t.ts': "import type { User } from '@prisma/client';\nexport const u: User = { id: '1', role: 'C' };\n",
        'apps/worker/src/bad.ts': write % 'B',
        'apps/api/src/a.ts': write % 'C',
        # the root package has no schema of its own: the first schema in use by path judges it, as before
        'scripts/seed.ts': write % 'C',
    })
    code, text = _static(tmp_path)
    assert code == 1 and _red_values(text) == [
        "apps/api/src/a.ts:2 User.role='C'  scripts/seed.ts:2 User.role='C'，允许 A|B（enum Role (apps/api/prisma/schema.prisma:1)）",
        "apps/worker/src/bad.ts:2 User.role='B'，允许 A|C（enum Role (apps/worker/prisma/schema.prisma:1)）"], text


def test_a_write_through_a_client_of_two_differing_schemas_is_left_unjudged_and_a_typed_object_keeps_its_schema(tmp_path):
    # r24 review (gate-4, gate-8): with two schemas in use of one package declaring User.role differently, a
    # `db2.user.create` through the second client was judged by the first schema; and a provider template with
    # the second schema's generator block took its output folder, so an object typed from that client was
    # judged by the first schema too.
    _commit(tmp_path, {
        'backend/package.json': '{"name": "backend"}',
        'backend/prisma/db1/schema.prisma': _role_schema('AB', '../../node_modules/@prisma-db-1/client'),
        'backend/prisma/db2/schema.prisma': _role_schema('AC', '../../node_modules/@prisma-db-2/client'),
        'backend/prisma/db2/schema.sqlite.prisma': _role_schema('AD', '../../node_modules/@prisma-db-2/client', 'sqlite'),
    })
    _write(tmp_path, {'backend/src/a.ts': """
        import { PrismaClient } from '@prisma-db-2/client';
        import type { User } from '@prisma-db-2/client';
        const db2 = new PrismaClient();
        export async function add(id: string) {
          await db2.user.create({ data: { id, role: 'C' } });
          await db2.user.create({ data: { id, role: 'Z' } });
        }
        export const a: User = { id: '1', role: 'C' };
        export const b: User = { id: '2', role: 'B' };
    """})
    code, text = _static(tmp_path)
    # which client a `user.create` goes through is not read: neither enum judges it
    assert code == 1 and _red_values(text) == [
        "backend/src/a.ts:9 User.role='B'，允许 A|C（enum Role (backend/prisma/db2/schema.prisma:6)）"], text


def test_an_import_of_a_generated_prisma_output_is_judged_by_its_own_schema(tmp_path):
    # r24 review (gate-2): Prisma 7's default output `generated/prisma` matched the generic client spelling
    # before the generator outputs were read, so the import never reached its own schema's set.
    _commit(tmp_path, {
        'prisma/schema.prisma': _role_schema('AB', '../src/generated/prisma'),
        'prisma/analytics/schema.prisma': _role_schema('AC', '../../src/generated/analytics'),
    })
    _write(tmp_path, {'src/a.ts': """
        import type { User } from './generated/prisma/client';
        import type { User as Event } from './generated/analytics';
        export const a: User = { id: '1', role: 'B' };
        export const b: User = { id: '2', role: 'C' };
        export const c: Event = { id: '3', role: 'B' };
    """})
    code, text = _static(tmp_path)
    assert code == 1 and _red_values(text) == [
        "src/a.ts:5 User.role='B'，允许 A|C（enum Role (prisma/analytics/schema.prisma:6)）",
        "src/a.ts:4 User.role='C'，允许 A|B（enum Role (prisma/schema.prisma:6)）"], text


def test_a_typescript_type_declared_with_different_sets_in_several_files_is_judged_by_its_own_declaration(tmp_path):
    # r24 review (gate-1): every `interface Props` of the project was judged by the first one by path.
    _commit(tmp_path, {
        'src/Badge.tsx': "export interface Props { variant: 'info' | 'warning' }\nexport const badge: Props = { variant: 'warning' };\n",
        'src/Button.tsx': "interface Props { variant: 'primary' | 'secondary' }\nexport const button: Props = { variant: 'primary' };\n",
        'src/Card.tsx': "interface Props { tone: 'flat' | 'raised' }\n",
    })
    _write(tmp_path, {
        'src/Button.tsx': "interface Props { variant: 'primary' | 'secondary' }\nexport const button: Props = { variant: 'primary' };\n"
                          "export const odd: Props = { variant: 'info' };\n",
        'src/Panel.tsx': "import type { Props } from './Badge';\nexport const panel: Props = { variant: 'primary' };\n",
        # no declaration in the file and none imported: which Props it is is unknown
        'src/Loose.tsx': "export const loose: Props = { variant: 'other' };\n",
        # a name declared once (or alike everywhere) judges every file, as before
        'src/Tile.tsx': "export const tile: Props = { tone: 'sunk' };\n",
    })
    code, text = _static(tmp_path)
    assert code == 1 and _red_values(text) == [
        "src/Tile.tsx:1 Props.tone='sunk'，允许 flat|raised（src/Card.tsx:1）",
        "src/Panel.tsx:2 Props.variant='primary'，允许 info|warning（src/Badge.tsx:1）",
        "src/Button.tsx:3 Props.variant='info'，允许 primary|secondary（src/Button.tsx:1）"], text
    with closing(build(tmp_path)) as graph:
        from flowguard.intent import health, owners
        names = sorted(issue.name for issue in health.values(owners.Change(_config(tmp_path), graph, None)).issues)
    assert names == ['values:Props.tone', 'values:Props.variant', 'values:Props.variant:src/Button.tsx'], names


def test_a_schema_in_use_whose_field_is_no_enum_leaves_its_own_writes_to_no_enum(tmp_path):
    # r25 check of the gate-5/gate-4 fix: only the schemas whose enum types the field took part, so a package
    # whose own schema in use types User.role as a String, and an object typed from that schema's client, were
    # still judged by another schema's enum.
    write = "export async function add(prisma: any, id: string) {\n  await prisma.user.create({ data: { id, role: '%s' } });\n}\n"
    root = tmp_path / 'packages'
    _commit(root, {
        'apps/api/package.json': '{"name": "api"}', 'apps/api/prisma/schema.prisma': _role_schema('AB'),
        'apps/worker/package.json': '{"name": "worker"}', 'apps/worker/prisma/schema.prisma': _role_schema(None),
    })
    _write(root, {
        'apps/worker/src/w.ts': write % 'Z',
        'apps/worker/src/t.ts': "import type { User } from '@prisma/client';\nexport const u: User = { id: '1', role: 'Z' };\n",
        'apps/api/src/a.ts': write % 'Z',
        # a package without a schema of its own: the first schema in use whose enum types the field, as before
        'scripts/seed.ts': write % 'Z',
    })
    code, text = _static(root)
    assert code == 1 and _red_values(text) == [
        "apps/api/src/a.ts:2 User.role='Z'  scripts/seed.ts:2 User.role='Z'，允许 A|B（enum Role (apps/api/prisma/schema.prisma:1)）"], text
    root = tmp_path / 'clients'
    _commit(root, {
        'backend/package.json': '{"name": "backend"}',
        'backend/prisma/db1/schema.prisma': _role_schema('AB', '../../node_modules/@prisma-db-1/client'),
        'backend/prisma/db2/schema.prisma': _role_schema(None, '../../node_modules/@prisma-db-2/client'),
    })
    _write(root, {'backend/src/a.ts': """
        import type { User } from '@prisma-db-2/client';
        import type { User as Account } from '@prisma-db-1/client';
        export const a: User = { id: '1', role: 'Z' };
        export const b: Account = { id: '2', role: 'Z' };
        export async function add(prisma: any, id: string) {
          await prisma.user.create({ data: { id, role: 'Z' } });
        }
    """})
    code, text = _static(root)
    # db2's String judges its own client's object by no enum; which client `prisma.user.create` goes through is
    # unknown while the package's two schemas type the field differently
    assert code == 1 and _red_values(text) == [
        "backend/src/a.ts:4 User.role='Z'，允许 A|B（enum Role (backend/prisma/db1/schema.prisma:6)）"], text


def test_a_typed_object_in_a_file_that_declares_its_type_without_a_set_is_not_judged_by_another_files_set(tmp_path):
    # r25 check of the gate-1 fix: only the declarations with a set of a member counted, so Card's own
    # `interface Props { variant: string }` object was judged by Badge's `variant: 'info' | 'warning'`.
    _commit(tmp_path, {
        'src/Badge.tsx': "export interface Props { variant: 'info' | 'warning' }\nexport const badge: Props = { variant: 'info' };\n",
    })
    _write(tmp_path, {
        'src/Card.tsx': "export interface Props { variant: string; size?: number }\n\nexport const cardDefaults: Props = { variant: 'outline' };\n",
        'src/Alert.tsx': "type Props = { variant: string };\nexport const alert: Props = { variant: 'filled' };\n",
        'src/Form.tsx': "class Props { variant = 'plain'; }\nexport const form: Props = { variant: 'boxed' };\n",
        'src/Deck.tsx': "import type { Props } from './Card';\nexport const deck: Props = { variant: 'stacked' };\n",
        'src/Panel.tsx': "import type { Props } from './Badge';\nexport const panel: Props = { variant: 'error' };\n",
        # no declaration in the file and none imported: the member's only set judges it, as before
        'src/Loose.tsx': "export const loose: Props = { variant: 'other' };\n",
        # a type declared inside a function is no declaration of the file
        'src/Inner.tsx': "export function make() {\n  type Props = { variant: string };\n  return 1;\n}\n",
    })
    with closing(build(tmp_path)) as graph:
        assert graph.ts_type_files()['Props'] == {'src/Alert.tsx', 'src/Badge.tsx', 'src/Card.tsx', 'src/Form.tsx'}
    code, text = _static(tmp_path)
    assert code == 1 and _red_values(text) == [
        "src/Loose.tsx:1 Props.variant='other'  src/Panel.tsx:2 Props.variant='error'，允许 info|warning（src/Badge.tsx:1）"], text


def test_typescript_sets_of_one_name_from_aliases_of_one_file_keep_apart_names(tmp_path):
    # r25 check of the gate-6 fix: a TS set's further name added the file its alias came from, so three
    # components' `interface Props { variant: XVariant }` of one variants.ts got two equal names and one
    # decision closed both.
    _commit(tmp_path, {
        'src/variants.ts': "export type BadgeVariant = 'info' | 'warning';\nexport type ButtonVariant = 'primary' | 'secondary';\n"
                           "export type LinkVariant = 'plain' | 'underline';\n",
        **{f'src/{name}.tsx': f"import type {{ {name}Variant }} from './variants';\ninterface Props {{ variant: {name}Variant }}\n"
                              f"export const {name.lower()}: Props = {{ variant: 'nope' }};\n" for name in ('Badge', 'Button', 'Link')},
    })
    with closing(build(tmp_path)) as graph:
        from flowguard.intent import health, owners
        names = sorted(issue.name for issue in health.values(owners.Change(_config(tmp_path), graph, None)).issues)
    assert names == ['values:Props.variant', 'values:Props.variant:src/Button.tsx', 'values:Props.variant:src/Link.tsx'], names
    sentence = 'The link component keeps the nope variant until the design review ends.'
    _write(tmp_path, {'docs/decisions.md': sentence + '\n', '.flowguard/ledger.toml': (
        '[structure."values:Props.variant:src/Link.tsx"]\ndecision = "the link component keeps the nope variant until the design review ends"\n'
        f'source = {{ file = "docs/decisions.md", text = "{sentence}" }}\n')})
    code, text = _static(tmp_path, '--all')
    assert code == 0 and "src/Badge.tsx:3 Props.variant='nope'" in text and "src/Button.tsx:3 Props.variant='nope'" in text \
        and 'src/Link.tsx:3' not in text, text


def test_a_guessed_schemas_enum_keeps_the_plain_name_beside_a_check_as_4_1_named_it(tmp_path):
    # r25 check of the gate-6 fix: 4.1 read every Prisma enum, a guessed template's too, before a CHECK, so its
    # one problem of the field was the enum's; the RC gave the plain name to the CHECK, and the problem a 4.1
    # decision had closed came back under the enum's file.
    schema = ('model Account {\n  id     String @id\n  status %s\n  @@map("accounts")\n}\n')
    _commit(tmp_path, {
        'prisma/schema.postgres.prisma': 'datasource db {\n  provider = "postgresql"\n  url      = env("DATABASE_URL")\n}\n\n'
                                         'enum Status {\n  open\n  closed\n  gone\n}\n\n' + schema % 'Status',
        'prisma/schema.sqlite.prisma': 'datasource db {\n  provider = "sqlite"\n  url      = env("DATABASE_URL")\n}\n\n' + schema % 'String',
        'prisma/migrations/001/migration.sql': "CREATE TABLE accounts (id TEXT, status TEXT CHECK (status IN ('open', 'closed')));\n",
        'src/a.ts': """
            export async function add(prisma: any, id: string) {
              await prisma.account.create({ data: { id, status: 'gone' } });
              await prisma.account.create({ data: { id, status: 'zzz' } });
            }
        """,
    })
    with closing(build(tmp_path)) as graph:
        from flowguard.intent import health, owners
        names = sorted(issue.name for issue in health.values(owners.Change(_config(tmp_path), graph, None)).issues)
    assert names == ['values:Account.status', 'values:Account.status:prisma/migrations/'], names
    sentence = 'Imported accounts keep the status zzz until the migration job maps them.'
    _write(tmp_path, {'docs/decisions.md': sentence + '\n', '.flowguard/ledger.toml': (
        '[structure."values:Account.status"]\ndecision = "imported accounts keep the status zzz until the migration job maps them"\n'
        f'source = {{ file = "docs/decisions.md", text = "{sentence}" }}\n')})
    code, text = _static(tmp_path, '--all')
    # the 4.1 decision closes the enum's problem, as in 4.1; the CHECK, which 4.1 did not read beside it, is open
    assert code == 0 and 'open|closed|gone' not in text and \
        "src/a.ts:2 Account.status='gone'  src/a.ts:3 Account.status='zzz'，允许 open|closed（CHECK prisma/migrations/001/migration.sql:1）" in text, text


def test_a_schema_folder_at_the_repository_root_keeps_its_name_in_the_brief(tmp_path):
    # r25 check: a schema folder is named by its folder, the repository root's `./`, and the session brief's
    # short names of its column and onDelete problems read `缺列 .` and `onDelete .`.
    source = 'datasource db {\n  provider = "postgresql"\n  url      = env("DATABASE_URL")\n}\n'
    user = ('model User {\n  id       String  @id\n  name     String\n  parentId String?\n'
            '  parent   User?   @relation("tree", fields: [parentId], references: [id], onDelete: Cascade)\n'
            '  children User[]  @relation("tree")\n}\n')
    _commit(tmp_path, {'package.json': '{"name": "app", "prisma": {"schema": "db/schema.prisma"}}\n',
                       'db/schema.prisma': source + '\n' + user, 'a.prisma': source,
                       'b.prisma': user.replace('  name     String\n', '').replace('Cascade', 'Restrict')})
    with closing(build(tmp_path)) as graph:
        from flowguard.intent import health, owners
        change = owners.Change(_config(tmp_path), graph, None)
        found = [(issue.name, issue.short) for issue in [*health.columns(change).issues, *health.delete_rules(change).issues]]
    assert found == [('columns:./~db/schema.prisma', '缺列 ./'), ('ondelete:./~db/schema.prisma', 'onDelete ./')], found


def test_archived_prisma_files_take_no_part_in_two_declarations_differ(tmp_path):
    # r24 review (gate-9): a release snapshot under docs/ was compared with the live enum and the lead advised
    # adding the new value to it.
    item = 'enum Kind {\n%s}\n\nmodel Item {\n  id   String @id\n  kind Kind\n  @@map("items")\n}\n'
    _commit(tmp_path, {
        'prisma/schema.prisma': item % '  A\n  B\n  C\n',
        'docs/release-1.0/schema.prisma': item % '  A\n  B\n',
        'docs/history/001.sql': "CREATE TABLE items (id TEXT, kind TEXT CHECK (kind IN ('A', 'B')));\n",
        'src/kinds.ts': "export const KINDS = ['A', 'B', 'C'] as const;\nexport type Kind = (typeof KINDS)[number];\n",
    })
    _write(tmp_path, {'prisma/schema.prisma': item % '  A\n  B\n  C\n  D\n'})
    code, text = _flowguard(tmp_path, 'check', '--static', '--leads')
    differ = [line for line in text.splitlines() if '两份声明不同' in line]
    assert code == 0 and len(differ) == 1 and 'docs/' not in differ[0] and "src/kinds.ts:2（'A' | 'B' | 'C'；少 'D'）" in differ[0], text


def test_a_prisma_client_type_under_an_alias_a_namespace_or_a_generator_output_is_gated_by_its_model(tmp_path):
    # 4.2 review: `{ Item as Row }` was marked a client type but gated as Row.kind, so never; `P.Item` of a
    # namespace import and a type imported from the generator's own output folder were not client types.
    _commit(tmp_path, {'prisma/schema.prisma': """
        generator client {
          provider = "prisma-client-js"
          output   = "../generated/db"
        }

        enum Kind {
          A
          B
        }

        model Item {
          id   String @id
          kind Kind
        }
    """})
    _write(tmp_path, {
        'src/alias.ts': """
            import type { Item as Row } from '@prisma/client';
            export const row: Row = { id: '1', kind: 'C' };
        """,
        'src/space.ts': """
            import * as P from '@prisma/client';
            import { Prisma } from '@prisma/client';
            export const one: P.Item = { id: '1', kind: 'D' };
            export const two = { id: '2', kind: 'E' } satisfies Prisma.Item;
            export const three = { id: '3', kind: 'F' } as P.ItemCreateInput;
        """,
        'src/output.ts': """
            import type { Item } from '../generated/db';
            export const four: Item = { id: '4', kind: 'G' };
        """,
        # a module that re-exports the client's types is not followed
        'src/models.ts': "export type { Item } from '@prisma/client';\n",
        'src/elsewhere.ts': """
            import type { Item } from './models';
            export const five: Item = { id: '5', kind: 'H' };
        """,
    })
    code, text = _static(tmp_path)
    assert code == 1 and _lines(text, '红：取值') == [
        "红：取值不在声明集合里：src/alias.ts:2 Item.kind='C'  src/output.ts:2 Item.kind='G'  src/space.ts:3 Item.kind='D'  "
        "src/space.ts:4 Item.kind='E'，允许 A|B（enum Kind (prisma/schema.prisma:6)） → 改用集合里的值；集合真要加值，"
        "先改那条声明（enum Kind (prisma/schema.prisma:6)）"], text


def test_value_sets_come_from_the_schemas_in_use_keep_checks_and_keep_typescript_types_apart(tmp_path):
    # Planning Tool 0.6.28 (round 21, V1/V2/P01): the enum of a SQLite template the generator never reads
    # gated the field and hid every CHECK; a frontend interface Demand was gated by the Prisma model Demand.
    files = {
        'backend/package.json': '{"name": "backend", "scripts": {"generate": "prisma generate && '
                                'prisma generate --schema=prisma/central/central.prisma"}}\n',
        'backend/prisma/schema.prisma': '''
            datasource db {
              provider = "sqlserver"
              url      = env("DATABASE_URL")
            }

            model Notice {
              id   String @id
              kind String
              @@map("notices")
            }

            model Demand {
              id   String @id
              unit String
              @@map("demands")
            }
        ''',
        'backend/prisma/schema.sqlite.prisma': '''
            datasource db {
              provider = "sqlite"
              url      = env("DATABASE_URL")
            }

            enum NoticeKind {
              CREATED
            }

            enum DemandUnit {
              FTE_MONTH
              HEADCOUNT
            }

            model Notice {
              id   String     @id
              kind NoticeKind
              @@map("notices")
            }

            model Demand {
              id   String     @id
              unit DemandUnit
              @@map("demands")
            }
        ''',
        'backend/prisma/central/central.prisma': '''
            datasource db {
              provider = "postgresql"
              url      = env("CENTRAL_URL")
            }

            enum Level {
              LOW
              HIGH
            }

            model Gauge {
              id    String @id
              level Level
              @@map("gauges")
            }
        ''',
        'backend/prisma/migrations/001/migration.sql': '''
            CREATE TABLE notices (id NVARCHAR(36), kind NVARCHAR(20) CHECK (kind IN ('CREATED', 'UPDATED')));
            CREATE TABLE demands (id NVARCHAR(36), unit NVARCHAR(20) CHECK (unit IN ('FTE_MONTH', 'HEADCOUNT')));
        ''',
        'backend/prisma/central/migrations/001/migration.sql': '''
            CREATE TABLE gauges (id TEXT, level TEXT CHECK (level IN ('LOW', 'HIGH', 'MID')));
        ''',
        'docs/history/old-setup.sql': '''
            CREATE TABLE notices (id NVARCHAR(36), kind NVARCHAR(20) CHECK (kind IN ('CREATED', 'ARCHIVED')));
        ''',
        'backend/src/types/notice.ts': '''
            export type NoticeKind = 'CREATED' | 'UPDATED' | 'DELETED';
        ''',
        'backend/src/notice.service.ts': '''
            export async function notify(prisma: any) {
              await prisma.notice.create({ data: { kind: 'UPDATED' } });
              await prisma.notice.create({ data: { kind: 'ARCHIVED' } });
              await prisma.gauge.create({ data: { level: 'MID' } });
            }
        ''',
        'frontend/package.json': '{"name": "frontend"}\n',
        'frontend/src/types.ts': '''
            export interface Demand { unit: 'FTE' | 'HOURS'; }
        ''',
        'frontend/src/demand.ts': '''
            import type { Demand } from './types';
            export const first: Demand = { unit: 'FTE' };
            export const second = { unit: 'DAYS' } as Demand;
        ''',
    }
    _commit(tmp_path, files)
    with closing(build(tmp_path)) as graph:
        assert graph.prisma_schemas_in_use() == {'backend/prisma/schema.prisma', 'backend/prisma/central/central.prisma'}
        sets = sorted((row['key'], row['field'], row['values'], row['kind']) for row in graph.value_sets())
        assert sets == [('Demand.unit', 'Demand.unit', ('FTE_MONTH', 'HEADCOUNT'), 'sql-check'),
                        ('Demand.unit', 'ts:Demand.unit', ('FTE', 'HOURS'), 'ts-type'),
                        ('Gauge.level', 'Gauge.level', ('LOW', 'HIGH'), 'prisma-enum'),
                        ('Gauge.level', 'Gauge.level', ('LOW', 'HIGH', 'MID'), 'sql-check'),
                        ('Notice.kind', 'Notice.kind', ('CREATED', 'UPDATED'), 'sql-check')], sets
    code, text = _static(tmp_path, '--all')
    values = [line for line in text.splitlines() if '取值：' in line]
    # 'UPDATED' is in the CHECK the database runs (the template enum lacks it); the archived description under
    # docs/ does not add 'ARCHIVED'; 'MID' passes the CHECK but not the enum of the schema in use; the frontend
    # Demand is judged by its own union only.
    assert values == [
        "1. 取值：取值不在声明集合里：frontend/src/demand.ts:3 Demand.unit='DAYS'，允许 FTE|HOURS（frontend/src/types.ts:1）",
        "2. 取值：取值不在声明集合里：backend/src/notice.service.ts:4 Gauge.level='MID'，允许 LOW|HIGH"
        "（enum Level (backend/prisma/central/central.prisma:6)）",
        "3. 取值：取值不在声明集合里：backend/src/notice.service.ts:3 Notice.kind='ARCHIVED'，允许 CREATED|UPDATED"
        "（CHECK backend/prisma/migrations/001/migration.sql:1）"], text
    differ = sorted(line for line in _lines(text, '线索：旧账 两份声明不同：'))
    assert differ == [
        "线索：旧账 两份声明不同：Gauge.level backend/prisma/central/central.prisma:6（'HIGH' | 'LOW'；少 'MID'）  "
        "backend/prisma/central/migrations/001/migration.sql:1（'HIGH' | 'LOW' | 'MID'） → 补上缺的值；那份描述不再使用，就写明或删掉它",
        "线索：旧账 两份声明不同：Notice.kind backend/prisma/migrations/001/migration.sql:1（'CREATED' | 'UPDATED'；少 'DELETED'）  "
        "backend/prisma/schema.sqlite.prisma:6（'CREATED'；少 'DELETED', 'UPDATED'）  backend/src/types/notice.ts:1"
        "（'CREATED' | 'DELETED' | 'UPDATED'） → 补上缺的值；那份描述不再使用，就写明或删掉它"], text


def _config(root):
    from flowguard.intent.config import load_config
    return load_config(root)


# ---- pairs across JS/TS calls resolved by name -------------------------------------------------------

def test_a_registered_typescript_pair_follows_calls_resolved_by_name(tmp_path):
    files = {
        'prisma/schema.prisma': '''
            model Central {
              id        String @id
              orgUnitId String
            }

            model Local {
              id     String @id
              unitId String
            }
        ''',
        'src/central.ts': '''
            export const centralService = {
              async move(prisma: any, id: string, unit: string) {
                await prisma.central.update({ where: { id }, data: { orgUnitId: unit } });
                await this.mirror(prisma, id, unit);
              },
              async mirror(prisma: any, id: string, unit: string) {
                await prisma.local.update({ where: { id }, data: { unitId: unit } });
              },
            };
        ''',
    }
    _commit(tmp_path, files)
    _write(tmp_path, {'src/owners.ts': '// flowguard: owner Central.orgUnitId with=Local.unitId\nexport {};\n'})
    code, text = _static(tmp_path)
    assert code == 0 and '配对没写' not in text, text            # move writes Local.unitId through this.mirror()
    _write(tmp_path, {'src/admin.ts': '''
        export async function editCentral(prisma: any, id: string, unit: string) {
          await prisma.central.update({ where: { id }, data: { orgUnitId: unit } });
        }
    '''})
    code, text = _static(tmp_path)
    assert code == 1, text
    assert _lines(text, '红：配对没写') == [
        '红：配对没写 Central.orgUnitId：src/admin.ts:2 editCentral（JS/TS 调用按名字解析） 写了 Central.orgUnitId，'
        '同一操作（调用方向上 3 层、再从那里向下 3 层）里没写 Local.unitId → 补写；有意只写一边，'
        '把函数加进 owner 行的 alone=函数名(理由)（owner 注释在 src/owners.ts:1）'], text


def test_the_pair_reds_of_two_owners_are_two_lines(tmp_path):
    _commit(tmp_path, {
        'prisma/schema.prisma': '''
            model Central {
              id        String @id
              orgUnitId String
            }

            model Local {
              id     String @id
              unitId String
            }

            model Project {
              id       String @id
              leaderId String
            }

            model Member {
              id   String @id
              role String
            }
        ''',
        'src/owners.ts': '// flowguard: owner Central.orgUnitId with=Local.unitId\n// flowguard: owner Project.leaderId with=Member.*\nexport {};\n',
    })
    _write(tmp_path, {'src/admin.ts': '''
        export async function editCentral(prisma: any, id: string, unit: string) {
          await prisma.central.update({ where: { id }, data: { orgUnitId: unit } });
        }

        export async function lead(prisma: any, id: string, leaderId: string) {
          await prisma.project.update({ where: { id }, data: { leaderId } });
        }
    '''})
    code, text = _static(tmp_path)
    assert code == 1, text
    red = _lines(text, '红：配对没写')
    assert [line.partition('：')[0] for line in red] == ['红', '红'] and len(red) == 2, text
    assert red[0].startswith('红：配对没写 Central.orgUnitId：src/admin.ts:2 editCentral') and '；' not in red[0].partition(' → ')[0], red
    assert red[1].startswith('红：配对没写 Project.leaderId：src/admin.ts:6 lead') and 'Central' not in red[1], red


def test_pytest_reports_a_pair_that_a_typescript_change_breaks(tmp_path):
    # Planning Tool 0.6.28 (round 21, V3/G29): the plugin counted only .py files as changes, so the root
    # pytest passed quietly while check --static had this task's pair reds.
    _commit(tmp_path, {
        'prisma/schema.prisma': '''
            model Central {
              id        String @id
              orgUnitId String
            }

            model Local {
              id     String @id
              unitId String
            }
        ''',
        'src/owners.ts': '// flowguard: owner Central.orgUnitId with=Local.unitId\nexport {};\n',
        'tests/test_ok.py': 'def test_ok():\n    assert True\n',
        'pyproject.toml': '[tool.pytest.ini_options]\ntestpaths = ["tests"]\n',
    })
    code, text = _pytest(tmp_path)
    assert code == 0 and '配对没写' not in text, text
    _write(tmp_path, {'src/admin.ts': '''
        export async function editCentral(prisma: any, id: string, unit: string) {
          await prisma.central.update({ where: { id }, data: { orgUnitId: unit } });
        }
    '''})
    code, text = _pytest(tmp_path)
    assert code == 1, text
    assert '红：配对没写 Central.orgUnitId：src/admin.ts:2 editCentral（JS/TS 调用按名字解析） 写了 Central.orgUnitId' in text, text


def test_the_value_gate_reads_the_fallback_of_a_nullish_default(tmp_path):
    # Planning Tool 0.6.28 (round 21, G16): `sourceType: input.sourceType ?? 'CSV_IMPORT'` was not judged,
    # `sourceType: 'CSV_IMPORT'` was red.
    _commit(tmp_path, {
        'prisma/schema.prisma': '''
            model Project {
              id         String @id
              sourceType String
              @@map("projects")
            }
        ''',
        'prisma/migrations/001/migration.sql': '''
            CREATE TABLE projects (id TEXT, sourceType TEXT CHECK (sourceType IN ('MANUAL', 'IMPORT')));
        ''',
    })
    _write(tmp_path, {'src/projects.ts': '''
        export async function create(prisma: any, input: any) {
          await prisma.project.create({ data: { sourceType: input.sourceType ?? 'MANUAL' } });
          await prisma.project.create({ data: { sourceType: input.sourceType ?? 'CSV_IMPORT' } });
          await prisma.project.create({ data: { sourceType: input.sourceType ?? input.fallback } });
        }
    '''})
    code, text = _static(tmp_path)
    assert code == 1, text
    assert [line.partition(' → ')[0] for line in _lines(text, '红：取值')] == [
        "红：取值不在声明集合里：src/projects.ts:3 Project.sourceType='CSV_IMPORT'，允许 MANUAL|IMPORT"
        "（CHECK prisma/migrations/001/migration.sql:1）"], text


def test_a_pair_limited_to_updates_does_not_hold_the_writes_that_make_a_row(tmp_path):
    # Planning Tool 0.6.28 (round 21, V4): the business references follow a SAP number when it changes; with
    # with= alone every function that creates an employee was red.
    _commit(tmp_path, {
        'prisma/schema.prisma': '''
            model Employee {
              id     String @id
              sapRef Int
            }

            model Opportunity {
              id            String @id
              responsibleNo Int
            }
        ''',
        'src/employees.ts': '''
            export async function hire(prisma: any, id: string, sap: number) {
              await prisma.employee.create({ data: { id, sapRef: sap } });
            }
            export async function renumber(prisma: any, id: string, old: number, sap: number) {
              await prisma.employee.update({ where: { id }, data: { sapRef: sap } });
              await prisma.opportunity.updateMany({ where: { responsibleNo: old }, data: { responsibleNo: sap } });
            }
            export async function fixNumber(prisma: any, id: string, sap: number) {
              await prisma.employee.update({ where: { id }, data: { sapRef: sap } });
            }
        ''',
    })
    owner = '// flowguard: owner Employee.sapRef with=Opportunity.responsibleNo on=update\nexport {};\n'
    _write(tmp_path, {'src/owners.ts': owner})
    code, text = _static(tmp_path)
    assert code == 1, text
    assert _lines(text, '红：配对没写') == [
        '红：配对没写 Employee.sapRef：src/employees.ts:9 fixNumber（JS/TS 调用按名字解析）（只查修改） 写了 Employee.sapRef，同一操作'
        '（调用方向上 3 层、再从那里向下 3 层）里没写 Opportunity.responsibleNo → 补写；有意只写一边，把函数加进 owner 行的 '
        'alone=函数名(理由)（owner 注释在 src/owners.ts:1）'], text
    _write(tmp_path, {'src/owners.ts': owner.replace('on=update', 'on=create')})
    code, text = _static(tmp_path)
    assert code == 1 and [line.partition('（JS/TS')[0] for line in _lines(text, '红：配对没写')] == [
        '红：配对没写 Employee.sapRef：src/employees.ts:2 hire'], text
    _write(tmp_path, {'src/owners.ts': owner.replace('on=update', 'on=later')})
    code, text = _static(tmp_path)
    assert code == 1 and 'on= is update or create and limits with=: owner Model.field with=Other.field on=update' in text, text


def test_an_owner_line_with_on_out_of_place_names_the_on_form():
    # Round 21 verification of V4: on= after alone=, or on= without with=, got only the general owner form,
    # which says nothing about on= and claims with= is missing.
    message = ('on= is update or create and limits with=: owner Model.field with=Other.field on=update '
               '(alone=function(reason) after it)')
    for line in ('// flowguard: owner A.b with=C.d alone=f(why) on=update\n', '// flowguard: owner A.b on=update\n',
                 '// flowguard: owner A.b writers=f on=create\n'):
        facts = anchors.foreign_owners(line, 'typescript/a.ts', 'a.ts')
        assert [issue['message'] for issue in facts['anchor_issues']] == [message], (line, facts)
    facts = anchors.foreign_owners('// flowguard: owner A.b with=C.d on=update alone=f(why)\n', 'typescript/a.ts', 'a.ts')
    assert [(row['on'], tuple(row['pairs']), tuple(row['alone'])) for row in facts['anchors']] == [
        ('update', ('C.d',), ('f(why)',))], facts


def test_a_pair_is_one_operation_when_a_caller_writes_both_fields_through_two_helpers(tmp_path):
    files = {
        'shop/__init__.py': '',
        'shop/store.py': '''
            # flowguard: owner hires.reserved with=hires.state=held
            def _reserve_row(db, hire_id):
                db.execute("UPDATE hires SET reserved = 1 WHERE id = ?", (hire_id,))


            def _hold_row(db, hire_id):
                db.execute("UPDATE hires SET state = 'held' WHERE id = ?", (hire_id,))


            def reserve(db, hire_id):
                _reserve_row(db, hire_id)
                _hold_row(db, hire_id)


            def release(db, hire_id):
                db.execute("UPDATE hires SET reserved = 0 WHERE id = ?", (hire_id,))
        ''',
        'pyproject.toml': '[tool.pytest.ini_options]\npythonpath = ["."]\n',
    }
    _commit(tmp_path, {name: text for name, text in files.items() if name != 'shop/store.py'})
    _write(tmp_path, {'shop/store.py': files['shop/store.py']})
    code, text = _static(tmp_path)
    assert code == 1, text
    # _reserve_row writes reserved alone, but its caller reserve writes state='held' through _hold_row
    assert _lines(text, '红：配对没写') == [
        '红：配对没写 hires.reserved：shop/store.py:16 release 写了 hires.reserved，同一操作（调用方向上 3 层、再从那里向下 3 层）里没写 '
        'hires.state=held → 补写；有意只写一边，把函数加进 owner 行的 alone=函数名(理由)（owner 注释在 shop/store.py:1）'], text


def test_show_a_model_field_lists_sql_file_writes_and_counts_the_lines_it_leaves_out(tmp_path):
    _commit(tmp_path, {
        'pyproject.toml': '[tool.flowguard]\nscreen_lines = 6\n',
        'prisma/schema.prisma': '''
            model Employee {
              id                   String @id
              organizationalUnitId String @map("organizational_unit_id")
              @@map("employees")
            }
        ''',
        'prisma/setup.sql': "INSERT INTO employees (id, organizational_unit_id) VALUES ('e1', 'u1');\n",
        'src/employee.ts': '''
            export async function moveEmployee(prisma: any, id: string, unit: string) {
              await prisma.employee.update({ where: { id }, data: { organizationalUnitId: unit } });
            }
            export function employeeDeferred(id: string) { return id; }
            export function employeeUnitLabel(id: string) { return id; }
            export function employeeUnitCode(id: string) { return id; }
            export function employeeUnitName(id: string) { return id; }
        ''',
    })
    code, text = _flowguard(tmp_path, 'show', 'Employee.organizationalUnitId')
    assert code == 0, text                  # a .sql statement's write row has a call line too (no KeyError)
    lines = text.splitlines()
    assert 'writes Employee.organizationalUnitId prisma/setup.sql:1 <module> (sql:insert)' in lines, text
    assert 'writes Employee.organizationalUnitId src/employee.ts:2 moveEmployee (update)' in lines, text
    # "employeeDeferred" is no red line; the overflow names the command that prints the rest
    assert len(lines) == 6 and lines[-1] == ('... 4 more lines: python -m flowguard show Employee.organizationalUnitId '
                                             '--full lists them all'), text
    code, full = _flowguard(tmp_path, 'show', 'Employee.organizationalUnitId', '--full')
    assert code == 0 and len(full.splitlines()) == 9 and 'employeeDeferred' in full and 'more lines' not in full, full


def test_a_pair_operation_stays_in_production_code_and_in_its_own_package(tmp_path):
    # Planning Tool 0.6.28 `removeRole` (round 21, G13/G15): a frontend page with the same method names and a
    # backend test that calls both service methods satisfied the pair; a test's fixture write was a pair red.
    _commit(tmp_path, {
        'backend/package.json': '{"name": "backend"}\n',
        'frontend/package.json': '{"name": "frontend"}\n',
        'backend/prisma/schema.prisma': '''
            model Unit {
              id         String  @id
              managerId  String?
              managerSap Int?
            }
        ''',
        'backend/src/unit.service.ts': '''
            export const unitService = {
              async setManager(prisma: any, id: string, sap: number) {
                await prisma.unit.update({ where: { id }, data: { managerId: id, managerSap: sap } });
              },
              async moveManager(prisma: any, id: string, sap: number) {
                await prisma.unit.update({ where: { id }, data: { managerId: id } });
                await this.mirrorSap(prisma, id, sap);
              },
              async mirrorSap(prisma: any, id: string, sap: number) {
                await prisma.unit.update({ where: { id }, data: { managerSap: sap } });
              },
              async removeManager(prisma: any, id: string) {
                await prisma.unit.updateMany({ where: { managerId: id }, data: { managerId: null } });
              },
              async dropManager(prisma: any, id: string) {
                await prisma.unit.updateMany({ where: { managerId: id }, data: { managerId: null } });
              },
            };
        ''',
        'frontend/src/UnitPage.tsx': '''
            export function UnitPage(api: any) {
              api.removeManager('u1');
              api.setManager('u1', 7);
              return null;
            }
        ''',
        'backend/tests/unit.service.test.ts': '''
            import { unitService } from '../src/unit.service';
            await prisma.unit.create({ data: { id: 'u1', managerId: 'm1' } });
            export async function roundTrip(prisma: any) {
              await unitService.dropManager(prisma, 'u1');
              await unitService.setManager(prisma, 'u1', 7);
            }
        ''',
    })
    _write(tmp_path, {'backend/src/owners.ts': '// flowguard: owner Unit.managerId with=Unit.managerSap\nexport {};\n'})
    code, text = _static(tmp_path)
    assert code == 1, text
    # moveManager reaches mirrorSap through `this` in its own package; the page's calls are the frontend's own
    # names, and the test that calls dropManager is not part of its operation; the test's fixture is no write to hold.
    assert _lines(text, '红：配对没写') == [
        '红：配对没写 Unit.managerId：backend/src/unit.service.ts:13 removeManager  backend/src/unit.service.ts:16 dropManager'
        '（JS/TS 调用按名字解析） 写了 Unit.managerId，同一操作（调用方向上 3 层、再从那里向下 3 层）里没写 Unit.managerSap'
        ' → 补写；有意只写一边，把函数加进 owner 行的 alone=函数名(理由)（owner 注释在 backend/src/owners.ts:1）'], text


def test_show_of_a_field_names_the_fields_its_writers_also_write_as_with_candidates(tmp_path):
    # Planning Tool 0.6.28 (round 21, P51/P22): PspElement.move changes parentPspId without hierarchyLevel;
    # registering the pair turns it red at once, but nothing pointed at the pair.
    _commit(tmp_path, {
        'prisma/schema.prisma': '''
            model Node {
              id        String  @id
              parentId  String?
              level     Int
              title     String
              createdAt DateTime
            }
        ''',
        'src/nodes.ts': '''
            export async function addRoot(prisma: any, id: string, title: string) {
              await prisma.node.create({ data: { id, parentId: null, level: 0, title, createdAt: new Date() } });
            }
            export async function addChild(prisma: any, id: string, parent: any, title: string) {
              await prisma.node.create({ data: { id, parentId: parent.id, level: parent.level + 1, title, createdAt: new Date() } });
            }
            export async function move(prisma: any, id: string, parentId: string) {
              await prisma.node.update({ where: { id }, data: { parentId } });
            }
        ''',
    })
    code, text = _flowguard(tmp_path, 'show', 'Node.parentId')
    assert code == 0, text
    # id and createdAt are bookkeeping that every writer sets
    assert _lines(text, 'with= candidate') == [
        'with= candidate (reference only): Node.level is written by 2 of the 3 functions that write Node.parentId; not by '
        'src/nodes.ts:8 move -> if the owner says they change together: // flowguard: owner Node.parentId with=Node.level',
        'with= candidate (reference only): Node.title is written by 2 of the 3 functions that write Node.parentId; not by '
        'src/nodes.ts:8 move -> if the owner says they change together: // flowguard: owner Node.parentId with=Node.title'], text


# ---- deletes that leave restricting children ---------------------------------------------------------

def test_a_new_hard_delete_names_the_children_it_leaves_once_per_function_and_parent(tmp_path):
    _planning(tmp_path)
    _commit(tmp_path, {
        'backend/prisma/notes.prisma': '''
            model EmployeeNote {
              id         String   @id
              employeeId String
              employee   Employee @relation(fields: [employeeId], references: [id], onDelete: NoAction)
            }

            model EmployeeBadge {
              id         String   @id
              employeeId String
              employee   Employee @relation(fields: [employeeId], references: [id], onDelete: NoAction)
            }

            model EmployeeLog {
              id         String   @id
              employeeId String
              employee   Employee @relation(fields: [employeeId], references: [id], onDelete: Cascade)
            }
        ''',
        'backend/src/services/notes.service.ts': '''
            export async function addNote(prisma: any, employeeId: string) {
              await prisma.employeeNote.create({ data: { employeeId } });
            }
            export async function purgeBadges(prisma: any) {
              await prisma.employeeBadge.deleteMany({});
            }
        ''',
    })
    _write(tmp_path, {'backend/src/services/hard-delete.service.ts': '''
        export async function hardDeleteEmployee(prisma: any, id: string) {
          const blockers = await prisma.authorityAssignment.count({ where: { OR: [{ employeeId: id }, { sourceRef: id }] } });
          if (blockers) throw new Error('blocked');
          await prisma.userRole.deleteMany({ where: { employeeId: id } });
          await prisma.auditEvent.updateMany({ where: { actorId: id }, data: { actorId: null } });
          await removeEmployeeRow(prisma, id);
        }
        async function removeEmployeeRow(prisma: any, id: string) {
          await prisma.employee.delete({ where: { id } });
          await prisma.employee.delete({ where: { id: 'archive-' + id } });
        }
    '''})
    code, text = _static(tmp_path)
    assert code == 0, text
    leads = _lines(text, '线索：删除没处理子表')
    assert len(leads) == 1, text
    assert leads[0].startswith('线索：删除没处理子表：backend/src/services/hard-delete.service.ts:9  '
                               'backend/src/services/hard-delete.service.ts:10 removeEmployeeRow 删 Employee，NoAction 子表 '), leads
    listed = leads[0].partition('NoAction 子表 ')[2].partition(' 在同一操作里')[0]
    # deleted (UserRole), counted inside OR (AuthorityAssignment), nulled (AuditEvent), Cascade (EmployeeLog) and a
    # table no code creates or updates rows in (EmployeeBadge) are not listed; the optional self relation
    # Employee.supervisor is (round 21, P12): one employee row is deleted and the copied create writes supervisorId.
    assert listed == 'Employee、EmployeeNote、EmployeeTransfer（3 个外键：decidedById、employeeId、requestedById）、Notification', listed
    assert '[structure."delete:backend/src/services/hard-delete.service.ts:removeEmployeeRow:Employee"]' in text, text


def test_an_optional_relation_over_a_required_key_restricts_the_delete(tmp_path):
    # Round 23 review: Prisma gives `unit Unit?` over `unitId String` ON DELETE RESTRICT (6.19 `migrate diff`);
    # only a relation whose key fields are all optional defaults to SetNull.
    _commit(tmp_path, {
        'prisma/schema.prisma': '''
            model Unit {
              id    String @id
              rooms Room[]
              desks Desk[]
            }

            model Room {
              id     String @id
              unitId String
              unit   Unit?  @relation(fields: [unitId], references: [id])
            }

            model Desk {
              id     String  @id
              unitId String?
              unit   Unit?   @relation(fields: [unitId], references: [id])
            }
        ''',
        'src/build.ts': '''
            export async function furnish(prisma: any, unitId: string) {
              await prisma.room.create({ data: { id: 'r', unitId } });
              await prisma.desk.create({ data: { id: 'd', unitId } });
            }
        ''',
    })
    _write(tmp_path, {'src/remove.ts': '''
        export async function removeUnit(prisma: any, id: string) {
          await prisma.unit.delete({ where: { id } });
        }
    '''})
    code, text = _static(tmp_path)
    assert code == 0 and _lines(text, '线索：删除没处理子表') == [
        '线索：删除没处理子表：src/remove.ts:2 removeUnit 删 Unit，Restrict 子表 Room 在同一操作里没删、没置空、没计数'
        '（调用按名字解析） → 删除前先删或置空这些子表的行，或先计数并拒绝删除；有意交给数据库拒绝，就把决定记进 '
        '.flowguard/ledger.toml：'], text


def test_a_one_row_delete_of_a_tree_the_code_builds_names_its_children(tmp_path):
    # Planning Tool 0.6.28 `demand.service.ts remove` (round 21, P12): a demand with forwarded child demands
    # (`parentDemandId`, NoAction) was deleted by id; optional self relations were skipped wholesale.
    _commit(tmp_path, {
        'prisma/schema.prisma': '''
            model Demand {
              id       String   @id
              parentId String?
              parent   Demand?  @relation("DemandTree", fields: [parentId], references: [id], onDelete: NoAction)
              children Demand[] @relation("DemandTree")
            }

            model Folder {
              id       String   @id
              parentId String?
              parent   Folder?  @relation("FolderTree", fields: [parentId], references: [id], onDelete: NoAction)
              children Folder[] @relation("FolderTree")
            }

            model Tag {
              id       String  @id
              parentId String?
              parent   Tag?    @relation("TagTree", fields: [parentId], references: [id], onDelete: NoAction)
              children Tag[]   @relation("TagTree")
            }
        ''',
        'src/build.ts': '''
            export async function forward(prisma: any, id: string) {
              await prisma.demand.create({ data: { id: id + '-f', parentId: id } });
              await prisma.folder.create({ data: { id: id + '-f', parentId: id } });
              await prisma.tag.create({ data: { id: id + '-t', parentId: null } });
            }
        ''',
    })
    _write(tmp_path, {'src/remove.ts': '''
        export async function removeDemand(prisma: any, id: string) {
          await prisma.demand.delete({ where: { id } });
        }
        export async function removeFolders(prisma: any, ids: string[]) {
          for (const id of ids) {
            await prisma.folder.delete({ where: { id } });
          }
          await prisma.folder.deleteMany({ where: { id: { in: ids } } });
        }
        export async function removeTag(prisma: any, id: string) {
          await prisma.tag.delete({ where: { id } });
        }
    '''})
    code, text = _static(tmp_path)
    assert code == 0, text
    # Folder rows go in a loop (hierarchy order) or all at once; no code links Tag rows into a tree.
    assert _lines(text, '线索：删除没处理子表') == [
        '线索：删除没处理子表：src/remove.ts:2 removeDemand 删 Demand，NoAction 子表 Demand 在同一操作里没删、没置空、没计数'
        '（调用按名字解析） → 删除前先删或置空这些子表的行，或先计数并拒绝删除；有意交给数据库拒绝，就把决定记进 '
        '.flowguard/ledger.toml：'], text


def test_a_tree_whose_parent_key_can_be_null_is_left_to_a_delete_of_many_rows_also_over_a_required_tenant_key(tmp_path):
    # r24 review (ondelete-3): a tree keyed by (tenantId, parentId), tenantId required, restricts by Prisma's
    # default; the tree exemption read that flag too, so `deleteMany` of a whole tenant's tree got a lead.
    _commit(tmp_path, {
        'prisma/schema.prisma': '''
            model Node {
              id       String  @id
              tenantId String
              parentId String?
              parent   Node?   @relation("tree", fields: [tenantId, parentId], references: [tenantId, id])
              children Node[]  @relation("tree")
              @@unique([tenantId, id])
            }
        ''',
        'src/build.ts': '''
            export async function add(prisma: any, tenantId: string, id: string, parentId: string) {
              await prisma.node.create({ data: { id, tenantId, parentId } });
            }
        ''',
    })
    _write(tmp_path, {'src/clear.ts': '''
        export async function clearTenant(prisma: any, tenantId: string) {
          await prisma.node.deleteMany({ where: { tenantId } });
        }
        export async function removeNode(prisma: any, id: string) {
          await prisma.node.delete({ where: { id } });
        }
    '''})
    code, text = _static(tmp_path)
    # the one-row delete of a tree the code builds still names its children
    assert code == 0 and _lines(text, '线索：删除没处理子表') == [
        '线索：删除没处理子表：src/clear.ts:5 removeNode 删 Node，Restrict 子表 Node（2 个外键：tenantId、parentId） '
        '在同一操作里没删、没置空、没计数（调用按名字解析） → 删除前先删或置空这些子表的行，或先计数并拒绝删除；有意交给数据库拒绝，'
        '就把决定记进 .flowguard/ledger.toml：'], text


def test_a_table_the_code_reads_or_deletes_but_never_fills_is_a_structure_problem(tmp_path):
    # Planning Tool 0.6.28 (round 21, P18): local DeputyAssignment is read and deleted, no code makes its rows.
    _commit(tmp_path, {
        'prisma/schema.prisma': '''
            model Deputy {
              id String @id
              @@map("deputies")
            }

            model Request {
              id     String @id
              status String
            }

            model Level {
              id   String @id
              name String
              @@map("levels")
            }

            model Note {
              id String @id
            }
        ''',
        'prisma/migrations/001/migration.sql': '''
            CREATE TABLE levels (id TEXT, name TEXT);
            INSERT INTO levels (id, name) VALUES ('1', 'low');
        ''',
        'docs/history/old.sql': "INSERT INTO deputies (id) VALUES ('d1');\n",
        'src/deputies.ts': '''
            export async function deputiesOf(prisma: any, id: string) {
              return prisma.deputy.findMany({ where: { id } });
            }
            export async function purge(prisma: any) {
              await prisma.deputy.deleteMany({ where: { id: 'old' } });
              await prisma.request.updateMany({ data: { status: 'CLOSED' } });
              return prisma.request.count({ where: { status: 'OPEN' } });
            }
            export async function notes(prisma: any) {
              await prisma.note.create({ data: { id: 'n' } });
              await prisma.level.findMany({ where: { name: 'low' } });
              return prisma.note.findMany({ where: { id: 'n' } });
            }
        ''',
        'tests/deputies.test.ts': '''
            await prisma.deputy.create({ data: { id: 'd1' } });
            await prisma.request.create({ data: { id: 'r1', status: 'OPEN' } });
        ''',
    })
    code, text = _static(tmp_path, '--all')
    found = [line for line in text.splitlines() if '建行：' in line]
    # Level rows come from a migration's INSERT, Note rows from code; a test fixture and an archived SQL file
    # under docs/ make no rows the application has.
    assert found == [
        '1. 建行：代码从不建行的表：Deputy 读 src/deputies.ts:2，删 src/deputies.ts:5，没有一处 create/upsert/INSERT',
        '2. 建行：代码从不建行的表：Request 读 src/deputies.ts:7，改 src/deputies.ts:6，没有一处 create/upsert/INSERT'], text
    assert '       [structure."uncreated:Deputy"]' in text, text
    source = tmp_path / 'src/deputies.ts'
    source.write_text(source.read_text().replace('where: { id } }', 'where: { id }, take: 5 }'))
    code, text = _static(tmp_path)
    assert _lines(text, '线索：未决结构问题：代码从不建行的表') == [
        '线索：未决结构问题：代码从不建行的表：Deputy 读 src/deputies.ts:2，删 src/deputies.ts:5，没有一处 create/upsert/INSERT'
        ' → 先告诉主人：这些行从哪里来（种子、迁移、外部系统）；没有来源就删掉这些读和删，有意如此就把决定记进 .flowguard/ledger.toml：'], text


def test_a_prisma_view_the_code_reads_is_not_a_table_without_rows(tmp_path):
    # Round 21 verification of P18: a Prisma `view` is read by design; no code makes its rows.
    _commit(tmp_path, {
        'prisma/schema.prisma': '''
            model User {
              id   String @id
              name String
            }

            view UserSummary {
              id    String @unique
              total Int
            }

            model Audit {
              id String @id
            }
        ''',
        'src/users.ts': '''
            export async function add(prisma: any) {
              await prisma.user.create({ data: { id: 'u', name: 'n' } });
              await prisma.audit.findMany({ where: { id: 'a' } });
              return prisma.userSummary.findMany({ where: { id: 'u' } });
            }
        ''',
    })
    code, text = _static(tmp_path, '--all')
    assert [line for line in text.splitlines() if '建行：' in line] == [
        '1. 建行：代码从不建行的表：Audit 读 src/users.ts:3，没有一处 create/upsert/INSERT'], text


# ---- fixed example 17: columns one description lacks -------------------------------------------------

def test_delete_rules_that_differ_between_two_schemas_are_one_structure_problem_and_a_lead_when_added(tmp_path):
    schema = """
        datasource db {
          provider = "%s"
          url      = env("DATABASE_URL")
        }

        model Unit {
          id    String @id
          rooms Room[]
        }

        model Room {
          id     String @id
          unitId String
          unit   Unit   @relation(fields: [unitId], references: [id], onDelete: %s)
        }
    """
    _commit(tmp_path, {'prisma/schema.prisma': schema % ('sqlserver', 'NoAction'),
                       'prisma/schema.sqlite.prisma': schema % ('sqlite', 'NoAction')})
    code, text = _static(tmp_path, '--all')
    assert code == 0 and 'onDelete 不同' not in text, text
    _write(tmp_path, {'prisma/schema.sqlite.prisma': schema % ('sqlite', 'Cascade')})
    code, text = _static(tmp_path)
    leads = _lines(text, '线索：onDelete 不同')
    assert code == 0 and leads == [
        '线索：onDelete 不同：prisma/schema.sqlite.prisma 对照 prisma/schema.prisma：这次新增 1 条关系（共 1 条；'
        '括号里先是 prisma/schema.prisma 的规则，再是这份的）：Room.unit（NoAction/Restrict / Cascade） → 让两份 schema 的删除规则一致，或让测试用的那份也照在用的那份删；'
        '有意不同（例如 SQL Server 不允许多条级联路径），就把决定记进 .flowguard/ledger.toml： '
        '[structure."ondelete:prisma/schema.prisma~prisma/schema.sqlite.prisma"] '
        'decision = "换成主人的决定：谁负责、为什么这样（不少于 8 个词）" source = "R<n>"'], text
    code, text = _static(tmp_path, '--all')
    assert '. 删除：onDelete 不同：prisma/schema.sqlite.prisma 对照 prisma/schema.prisma' in text, text


ROOMS = '''
    datasource db {
      provider = "%s"
      url      = env("DATABASE_URL")
    }

    model Unit {
      id    String @id
      %s
    }
'''
ROOM = '''
    model %s {
      id     String @id
      unitId String
      unit   Unit   @relation(fields: [unitId], references: [id], onDelete: %s)
    }
'''


def _rooms(provider, rules, extra=''):
    """A schema whose Unit has one child model per (name, onDelete) of `rules`."""
    back = '\n      '.join(f'{name.lower()}s {name}[]' for name, _ in rules)
    return textwrap.dedent(ROOMS % (provider, back)) + ''.join(textwrap.dedent(ROOM % item) for item in rules) + extra


def test_the_ondelete_lead_names_the_relations_the_change_added_and_the_listing_names_all(tmp_path):
    # Round 23 review: the lead printed the first six relations by name, not the one the change added, and
    # --all cut the pair to six with no way to see the rest.
    old = [(name, 'NoAction') for name in ('Alpha', 'Bravo', 'Charlie', 'Delta', 'Echo', 'Foxtrot', 'Golf')]
    _commit(tmp_path, {'prisma/schema.prisma': _rooms('sqlserver', [*old, ('Zulu', 'NoAction')]),
                       'prisma/schema.sqlite.prisma': _rooms('sqlite', [(name, 'Cascade') for name, _ in old] + [('Zulu', 'NoAction')])})
    _write(tmp_path, {'prisma/schema.sqlite.prisma': _rooms('sqlite', [(name, 'Cascade') for name, _ in old] + [('Zulu', 'SetNull')])})
    code, text = _static(tmp_path)
    leads = _lines(text, '线索：onDelete 不同')
    assert code == 0 and len(leads) == 1, text
    assert leads[0].startswith('线索：onDelete 不同：prisma/schema.sqlite.prisma 对照 prisma/schema.prisma：这次新增 1 条关系'
                               '（共 8 条；括号里先是 prisma/schema.prisma 的规则，再是这份的）：Zulu.unit（NoAction/Restrict / SetNull） → '), leads
    code, text = _static(tmp_path, '--all')
    listed = next(line for line in text.splitlines() if '. 删除：onDelete 不同' in line)
    assert listed.endswith('：8 条关系（括号里先是 prisma/schema.prisma 的规则，再是这份的）：'
                           + '、'.join(f'{name}.unit（NoAction/Restrict / Cascade）' for name, _ in old)
                           + '、Zulu.unit（NoAction/Restrict / SetNull）'), listed


def test_an_ondelete_pair_keeps_its_name_and_its_decision_when_the_other_schema_becomes_the_larger(tmp_path):
    # Round 23 review: the pair is read against the larger of two schemas in use; tables added to the smaller
    # one turned the pair round, renamed the problem and voided the owner's decision.
    a = _rooms('sqlserver', [('Room', 'NoAction')], 'model Hall {\n  id String @id\n}\n')
    b = _rooms('sqlserver', [('Room', 'Cascade')])
    _commit(tmp_path, {'prisma/a.prisma': a, 'prisma/b.prisma': b})
    code, text = _static(tmp_path, '--all')
    assert '. 删除：onDelete 不同：prisma/b.prisma 对照 prisma/a.prisma：1 条关系' in text, text
    name = next(line.strip() for line in text.splitlines() if line.strip().startswith('[structure."ondelete:'))
    assert name == '[structure."ondelete:prisma/a.prisma~prisma/b.prisma"]', text
    _write(tmp_path, {'prisma/b.prisma': b + 'model Shed {\n  id String @id\n}\n\nmodel Barn {\n  id String @id\n}\n'})
    code, text = _static(tmp_path, '--all')
    assert '. 删除：onDelete 不同：prisma/a.prisma 对照 prisma/b.prisma：1 条关系' in text, text
    assert '[structure."ondelete:prisma/a.prisma~prisma/b.prisma"]' in text, text
    code, text = _static(tmp_path)
    assert not _lines(text, '线索：onDelete 不同'), text             # the change added no difference
    _write(tmp_path, {'docs/decisions.md': 'The SQL Server schema keeps NoAction because of multiple cascade paths.\n',
                      '.flowguard/ledger.toml': name + '\ndecision = "the second schema cascades on purpose, the owner keeps both"\n'
                      'source = { file = "docs/decisions.md", text = "The SQL Server schema keeps NoAction because of multiple cascade paths." }\n'})
    code, text = _static(tmp_path, '--all')
    assert code == 0 and 'onDelete 不同' not in text, text


def test_a_change_to_either_schema_of_an_open_ondelete_pair_gets_the_touched_lead(tmp_path):
    _commit(tmp_path, {'prisma/schema.prisma': _rooms('sqlserver', [('Room', 'NoAction')]),
                       'prisma/schema.sqlite.prisma': _rooms('sqlite', [('Room', 'Cascade')])})
    for file in ('prisma/schema.sqlite.prisma', 'prisma/schema.prisma'):
        path = tmp_path / file
        saved = path.read_text(encoding='utf-8')
        path.write_text(saved + '// reviewed\n', encoding='utf-8')
        code, text = _static(tmp_path)
        assert code == 0 and _lines(text, '线索：未决结构问题：onDelete 不同') == [
            '线索：未决结构问题：onDelete 不同：prisma/schema.sqlite.prisma 对照 prisma/schema.prisma：1 条关系（括号里先是 '
            'prisma/schema.prisma 的规则，再是这份的）：Room.unit（NoAction/Restrict / Cascade） → 让两份 schema 的删除规则一致，'
            '或让测试用的那份也照在用的那份删；有意不同（例如 SQL Server 不允许多条级联路径），就把决定记进 .flowguard/ledger.toml：'], (file, text)
        path.write_text(saved, encoding='utf-8')


def _mapped(schema, how):
    return schema.replace('unitId String\n', 'unitId String @map("unit_id")\n') if how == '@map' else \
        schema.replace('onDelete: NoAction)\n}\n', 'onDelete: NoAction)\n  @@map("rooms")\n}\n').replace(
            'onDelete: Cascade)\n}\n', 'onDelete: Cascade)\n  @@map("rooms")\n}\n')


@pytest.mark.parametrize('how', ['@map', '@@map'])
def test_a_mapping_added_to_both_schemas_adds_no_ondelete_difference(tmp_path, how):
    # Round 23 check: renaming the key column or the table in both schemas left the difference as it was, yet the
    # lead called Room.unit newly added; the change only touches the open problem.
    old, template = _rooms('sqlserver', [('Room', 'NoAction')]), _rooms('sqlite', [('Room', 'Cascade')])
    _commit(tmp_path, {'prisma/schema.prisma': old, 'prisma/schema.sqlite.prisma': template})
    _write(tmp_path, {'prisma/schema.prisma': _mapped(old, how), 'prisma/schema.sqlite.prisma': _mapped(template, how)})
    assert _mapped(old, how) != old and _mapped(template, how) != template
    code, text = _static(tmp_path)
    leads = [lead for lead in _lines(text, '线索：') if 'onDelete' in lead]
    assert code == 0 and len(leads) == 1 and leads[0].startswith(
        '线索：未决结构问题：onDelete 不同：prisma/schema.sqlite.prisma 对照 prisma/schema.prisma：1 条关系'), text


def test_a_schema_that_drops_a_relation_but_keeps_its_key_column_has_no_foreign_key(tmp_path):
    # Round 23 check: the side without the foreign key was shown by no test; its table, key column and parent
    # stay, so deleting a Unit there leaves the rooms pointing nowhere.
    _commit(tmp_path, {'prisma/schema.prisma': _rooms('sqlserver', [('Room', 'NoAction')]),
                       'prisma/schema.sqlite.prisma': _rooms('sqlite', [('Room', 'NoAction')])})
    template = _rooms('sqlite', [('Room', 'NoAction')]).replace(
        '  unit   Unit   @relation(fields: [unitId], references: [id], onDelete: NoAction)\n', '').replace('rooms Room[]', '')
    _write(tmp_path, {'prisma/schema.sqlite.prisma': template})
    code, text = _static(tmp_path)
    assert code == 0 and [lead.partition(' → ')[0] for lead in _lines(text, '线索：onDelete 不同')] == [
        '线索：onDelete 不同：prisma/schema.sqlite.prisma 对照 prisma/schema.prisma：这次新增 1 条关系（共 1 条；括号里先是 '
        'prisma/schema.prisma 的规则，再是这份的）：Room.unit（NoAction/Restrict / 没有外键）'], text
    code, text = _static(tmp_path, '--all')
    assert next(line for line in text.splitlines() if '. 删除：onDelete 不同' in line).endswith(
        '：1 条关系（括号里先是 prisma/schema.prisma 的规则，再是这份的）：Room.unit（NoAction/Restrict / 没有外键）'), text
    assert '缺列' not in text, text                    # the table and its key column are there


UNITS = '''
    datasource db {
      provider = "%s"
      url      = env("DATABASE_URL")
    }

    model Unit {
      id   String @id
      name String%s
    }
'''
LABELS = "export const %s = { BU: 'Business Unit', TEAM: 'Team', AREA: '%s' };\n"
# kind: (baseline, the change that adds the problem, the lead's start, the problem's name)
ADDED = {
    'deletes': ({'prisma/schema.prisma': _rooms('sqlserver', [('Room', 'NoAction')]),
                 'src/rooms.ts': "export async function addRoom(prisma: any, unitId: string) {\n"
                                 "  await prisma.room.create({ data: { id: 'r', unitId } });\n}\n"},
                {'src/remove.ts': "export async function removeUnit(prisma: any, id: string) {\n"
                                  "  await prisma.unit.delete({ where: { id } });\n}\n"},
                '删除没处理子表', 'delete:src/remove.ts:removeUnit:Unit'),
    'columns': ({'prisma/schema.prisma': UNITS % ('sqlserver', ''), 'prisma/schema.sqlite.prisma': UNITS % ('sqlite', '')},
                {'prisma/schema.prisma': UNITS % ('sqlserver', '\n      code String')},
                '几份描述之间缺的列', 'columns:prisma/schema.sqlite.prisma~prisma/schema.prisma'),
    'ondelete': ({'prisma/schema.prisma': _rooms('sqlserver', [('Room', 'NoAction')]),
                  'prisma/schema.sqlite.prisma': _rooms('sqlite', [('Room', 'NoAction')])},
                 {'prisma/schema.sqlite.prisma': _rooms('sqlite', [('Room', 'Cascade')])},
                 'onDelete 不同', 'ondelete:prisma/schema.prisma~prisma/schema.sqlite.prisma'),
    'labels': ({'src/a.ts': LABELS % ('TYPE_LABELS', 'Area'), 'src/b.ts': LABELS % ('KIND_LABELS', 'Area')},
               {'src/b.ts': LABELS % ('KIND_LABELS', 'Areas')},
               '标签表不一致', 'labels:src/a.ts:TYPE_LABELS'),
}


@pytest.mark.parametrize('kind', sorted(ADDED))
def test_a_structure_problem_the_owner_decided_gets_no_lead_when_a_change_adds_it(tmp_path, kind):
    # Round 23 review: a decision in [structure] closed the problem in --all, but a change that added to it
    # still got the lead with a ledger entry to copy, which would have duplicated the decided table.
    before, change, start, name = ADDED[kind]
    _commit(tmp_path, before)
    base = _git(tmp_path, 'rev-parse', 'HEAD').strip()
    _write(tmp_path, change)
    def leads():
        from flowguard.intent import owners
        cfg = _config(tmp_path)
        with closing(build(cfg.root, roots=cfg.roots)) as graph:
            return [lead for lead in owners.static_findings(cfg, graph, anchors.collect(graph), base).leads if lead.startswith(start)]
    assert len(leads()) == 1, kind
    sentence = 'The owner keeps this difference on purpose and reviews it every release.'
    _write(tmp_path, {'docs/decisions.md': sentence + '\n', '.flowguard/ledger.toml': (
        f'[structure."{name}"]\ndecision = "the owner keeps this difference on purpose and reviews it every release"\n'
        f'source = {{ file = "docs/decisions.md", text = "{sentence}" }}\n')})
    assert leads() == [], kind


def test_fixed_17_missing_columns_between_prisma_and_init_sql_are_listed_one_by_one(tmp_path):
    _planning(tmp_path)
    init = tmp_path / 'backend/prisma/central/init-azure-sql.sql'
    saved = init.read_bytes()
    init.unlink()
    _commit(tmp_path)
    init.write_bytes(saved)
    code, text = _static(tmp_path)
    assert code == 0, text
    lead = next(line for line in _lines(text, '线索：几份描述之间缺的列') if 'central/schema.prisma' in line)
    assert lead.startswith('线索：几份描述之间缺的列：backend/prisma/central/init-azure-sql.sql 对照 '
                           'backend/prisma/central/schema.prisma：'), lead
    for column in ('central_sync_attempted_at', 'central_sync_error', 'central_sync_state', 'external_type',
                   'personnel_lifecycle_state', 'personnel_source', 'storage_scope'):
        assert column in lead, (column, lead)
    assert '没有表 central_lending_assignments' in lead, lead
    code, text = _static(tmp_path, '--all')
    assert any(line.startswith('线索：') is False and '缺列：几份描述之间缺的列：backend/prisma/central/init-azure-sql.sql' in line
               for line in text.splitlines()), text


# ---- fixed example 16: label drift, also in the generated vitest test --------------------------------

def _node():
    node = shutil.which('node')
    assert node, 'node is required to run the generated npm test file (GitHub runners and this machine have it)'
    return node


def _run_generated(root, target, env=None):
    stub = root / 'node_modules/vitest'
    stub.mkdir(parents=True, exist_ok=True)
    (stub / 'package.json').write_text('{"name": "vitest", "type": "module", "exports": "./index.js"}\n')
    (stub / 'index.js').write_text(STUB_VITEST)
    runner = root.parent / (root.name + '-run.mjs')
    runner.write_text(RUN_STUB)
    environment = dict(os.environ, PYTHONPATH=SOURCE + os.pathsep + os.environ.get('PYTHONPATH', ''), **(env or {}))
    return subprocess.run([_node(), str(runner), str(target)], cwd=root, capture_output=True, encoding='utf-8', timeout=240,
                          env=environment)


def test_fixed_16_the_label_drift_is_a_lead_in_check_static_and_in_the_generated_vitest_test(tmp_path):
    root = _planning(tmp_path / 'pt')
    frontend = root / 'frontend/src/utils/organization-navigation.ts'
    saved = frontend.read_bytes()
    frontend.unlink()
    _commit(root, {'package.json': '{"name": "pt", "private": true, "scripts": {"test": "vitest run"}, '
                                   '"devDependencies": {"vitest": "2.1.9"}}\n'})
    frontend.write_bytes(saved)
    code, text = _static(root)
    assert code == 0, text
    drift = next(line for line in _lines(text, '线索：标签写法不一致') if 'My Organization' in line)
    assert "'My Organization'（backend/src/services/authority/organization-navigation.ts:" in drift, drift
    assert "'My organization'（frontend/src/utils/organization-navigation.ts:" in drift and '这次新增的写法' in drift, drift
    code, text = _flowguard(root, 'init')
    assert code == 0 and 'Generated flowguard.static.test.mjs (vitest)' in text, text
    generated = root / 'flowguard.static.test.mjs'
    assert "import { test } from 'vitest';" in generated.read_text(encoding='utf-8')
    run = _run_generated(root, generated)
    output = _text(run.stdout + run.stderr)
    assert run.returncode == 0 and 'PASS FlowGuard check --static' in output, output
    assert drift in output, output                             # the same lead, printed by the npm test
    _write(root, {'backend/src/services/notice.service.ts': '''
        export async function notice(prisma: any) {
          await prisma.auditEvent.create({ data: { severity: 'WARN' } });
        }
    '''})
    _planning(root, 'planning_tool_static')
    run = _run_generated(root, generated)
    output = _text(run.stdout + run.stderr)
    assert run.returncode == 1 and 'FAIL FlowGuard check --static: FlowGuard check --static exit 1' in output, output
    assert "backend/src/services/notice.service.ts:2 AuditEvent.severity='WARN'，允许 INFO|WARNING|ERROR|CRITICAL" in output, output
    run = _run_generated(root, generated, env=dict(FLOWGUARD_PYTHON=str(tmp_path / 'no-such-python')))
    output = _text(run.stdout + run.stderr)
    assert run.returncode == 1 and 'no Python that can import flowguard was found' in output, output
    assert 'set FLOWGUARD_PYTHON' in output and 'no-such-python' in output, output


def test_the_files_init_writes_bring_no_label_spellings_of_their_own(tmp_path):
    _commit(tmp_path, {
        'package.json': '{"name": "app", "type": "module", "scripts": {"test": "vitest run"}, "devDependencies": {"vitest": "4.1.11"}}\n',
        # Each spelling has the key and the kind (literal_shape) of one only init's files hold: 'python', '--root'
        # and 'win32'. Without the exclusion each pair would be a new label lead.
        'src/flags.ts': "export function known(x: string): boolean {\n  return x === 'Python' || x === '--Root' || x === 'Win32';\n}\n",
    })
    code, text = _flowguard(tmp_path, 'init')
    assert code == 0 and 'Generated flowguard.static.test.mjs (vitest)' in text, text
    generated = (tmp_path / 'flowguard.vitest.mjs').read_text(encoding='utf-8')
    assert all(f"'{spelling}'" in generated for spelling in ('python', '--root', 'win32')), generated   # else the test says nothing
    code, text = _static(tmp_path)          # init's 'python', '--root' and 'win32' are FlowGuard's, not the project's labels
    assert code == 0 and not _lines(text, '线索：标签写法不一致'), text
    code, text = _static(tmp_path, '--all')
    assert 'flowguard.static.test.mjs' not in text and 'flowguard.vitest.mjs' not in text, text


def test_check_static_all_lists_label_spellings_the_baseline_already_had(tmp_path):
    root = _planning(tmp_path / 'pt')
    _commit(root, {})                          # both spellings are old: nothing new to report
    code, text = _static(root)
    assert code == 0 and not _lines(text, '线索：标签写法不一致'), text
    code, text = _static(root, '--all')
    old = next(line for line in _lines(text, '线索：旧账 标签写法不一致') if 'My Organization' in line)
    assert "'My organization'（frontend/src/utils/organization-navigation.ts:" in old and '这次新增的写法' not in old, old


def test_check_static_all_puts_the_new_lead_first_and_names_the_command_that_lists_every_lead(tmp_path):
    words = ['Alpha', 'Bravo', 'Charlie', 'Delta', 'Echo', 'Foxtrot', 'Golf', 'Hotel', 'India', 'Juliet', 'Kilo', 'Lima']
    _commit(tmp_path, {
        'src/upper.ts': ''.join(f"export function is{word}(x: string) {{ return x === '{word} Label'; }}\n" for word in words),
        'src/lower.ts': ''.join(f"export function was{word}(x: string) {{ return x === '{word.lower()} label'; }}\n" for word in words),
        'src/gamma.ts': "export function isGamma(x: string) { return x === 'Gamma Ray'; }\n",
    })
    # a label spelled another way ('Gamma ray'), not a key ('gamma-ray' is of another kind: literal_shape)
    _write(tmp_path, {'src/ray.ts': "export function isRay(x: string) { return x === 'Gamma ray'; }\n"})
    code, text = _static(tmp_path, '--all')
    leads = _lines(text, '线索：')
    assert code == 0 and leads[0].startswith("线索：标签写法不一致：'Gamma Ray'"), text       # the new one first
    assert "'Gamma ray'（src/ray.ts:1，这次新增的写法）" in leads[0], leads
    assert leads[-1].startswith('线索：另 ') and leads[-1].endswith('条：python -m flowguard check --static --all --leads 列出全部线索'), leads
    code, text = _static(tmp_path, '--all', '--leads')
    every = _lines(text, '线索：')
    assert code == 0 and len(every) == 13 and every[0] == leads[0] and not any(line.startswith('线索：另 ') for line in every), text
    assert all(line.startswith('线索：旧账 标签写法不一致') for line in every[1:]), every
    code, text = _static(tmp_path)
    assert code == 0 and _lines(text, '线索：') == [leads[0]], text


def test_the_overflow_of_a_run_against_base_names_that_base_in_the_command_that_lists_every_lead(tmp_path):
    words = ['Alpha', 'Bravo', 'Charlie', 'Delta', 'Echo', 'Foxtrot', 'Golf', 'Hotel', 'India', 'Juliet', 'Kilo', 'Lima']
    _commit(tmp_path, {'src/upper.ts': ''.join(f"export function is{word}(x: string) {{ return x === '{word} Label'; }}\n"
                                               for word in words)})
    _write(tmp_path, {'src/lower.ts': ''.join(f"export function was{word}(x: string) {{ return x === '{word.lower()} label'; }}\n"
                                              for word in words)})
    _commit(tmp_path, message='twelve new spellings')
    # Against HEAD nothing is new; against HEAD~1 the twelve spellings are: the listing command keeps that base.
    code, text = _static(tmp_path, '--base', 'HEAD~1')
    leads = _lines(text, '线索：')
    assert code == 0 and leads[-1].endswith('条：python -m flowguard check --static --base HEAD~1 --leads 列出全部线索'), leads
    code, text = _static(tmp_path, '--base', 'HEAD~1', '--leads')
    assert code == 0 and len(_lines(text, '线索：')) == 12, text


def test_the_overflow_of_a_pytest_session_against_flowguard_base_keeps_that_base_as_base(tmp_path):
    words = ['Alpha', 'Bravo', 'Charlie', 'Delta', 'Echo', 'Foxtrot', 'Golf', 'Hotel', 'India', 'Juliet', 'Kilo', 'Lima']
    _commit(tmp_path, {'src/upper.ts': ''.join(f"export function is{word}(x: string) {{ return x === '{word} Label'; }}\n"
                                               for word in words),
                       'pyproject.toml': '[tool.pytest.ini_options]\npythonpath = ["."]\ntestpaths = ["tests"]\n',
                       'tests/test_ok.py': 'def test_ok():\n    pass\n'})
    _write(tmp_path, {'src/lower.ts': ''.join(f"export function was{word}(x: string) {{ return x === '{word.lower()} label'; }}\n"
                                              for word in words)})
    _commit(tmp_path, message='twelve new spellings')
    # The session's leads are against HEAD~1; the command that lists them all must be too.
    code, text = _pytest(tmp_path, '--flowguard-base', 'HEAD~1')
    leads = _lines(text, '线索：')
    assert code == 0 and leads[-1].endswith('条：python -m flowguard check --static --base HEAD~1 --leads 列出全部线索'), text


def test_the_overflow_of_show_spells_a_phrase_query_so_cmd_exe_reads_it_too(tmp_path):
    _commit(tmp_path, {
        'pyproject.toml': '[tool.flowguard]\nscreen_lines = 3\n',
        'src/unit.ts': ''.join(f'export function employeeUnit{name}(id: string) {{ return id; }}\n'
                               for name in ('Label', 'Code', 'Name', 'Path')),
    })
    code, text = _flowguard(tmp_path, 'show', 'employee unit')
    # single quotes ('employee unit') are no quotes in cmd.exe: the owner's Windows console would split the query
    assert code == 0 and text.splitlines()[-1].endswith(
        'more lines: python -m flowguard show "employee unit" --full lists them all'), text


def test_init_writes_a_jest_test_for_a_jest_project_and_keeps_a_foreign_file(tmp_path):
    _commit(tmp_path, {'web/package.json': '{"name": "web", "scripts": {"test": "jest"}, "devDependencies": {"jest": "29.7.0"}}\n'})
    code, text = _flowguard(tmp_path, 'init')
    generated = tmp_path / 'web/flowguard.static.test.js'
    assert code == 0 and 'Generated web/flowguard.static.test.js (jest)' in text, text
    body = generated.read_text(encoding='utf-8')
    assert "require('node:child_process')" in body and 'path.resolve(__dirname, "..")' in body and 'vitest' not in body, body
    # the interpreter that ran init is read from the git-ignored cache, never written into the committed file
    assert 'FLOWGUARD_PYTHON' in body and sys.executable not in body and '".flowguard/cache/python"' in body, body
    assert (tmp_path / '.flowguard/cache/python').read_text(encoding='utf-8') == sys.executable
    generated.write_text('test("mine", () => {});\n')
    code, text = _flowguard(tmp_path, 'init')
    assert code == 2 and 'an existing file has this name' in text, text


# ---- the open structure problems: decisions, touched leads and the brief -----------------------------

WRITERS = {
    'shop/__init__.py': '',
    'shop/models.py': '''
        class Job:
            status = 'new'
    ''',
    'shop/close.py': '''
        from shop.models import Job


        def close(job: Job):
            job.status = 'closed'
    ''',
    'shop/hold.py': '''
        from shop.models import Job


        def hold(job: Job):
            job.status = 'held'
    ''',
    'shop/reopen.py': '''
        from shop.models import Job


        def reopen(job: Job):
            job.status = 'open'
    ''',
    'tests/test_shop.py': '''
        from shop.close import close
        from shop.models import Job


        def test_close():
            job = Job()
            close(job)
            assert job.status == 'closed'
    ''',
    'pyproject.toml': '[tool.pytest.ini_options]\npythonpath = ["."]\ntestpaths = ["tests"]\n',
}


def _pytest(root, *options):
    bootstrap = ('import sys; sys.path.insert(0,sys.argv.pop(1)); import pytest; '
                 'raise SystemExit(pytest.main(sys.argv[1:]))')
    result = subprocess.run([sys.executable, '-c', bootstrap, SOURCE, '-q', '-p', 'flowguard.intent.plugin', *options], cwd=root,
                            capture_output=True, text=True, timeout=120, env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'))
    return result.returncode, _text(result)


def test_a_change_that_touches_an_open_structure_problem_gets_one_lead(tmp_path):
    _commit(tmp_path, WRITERS)
    code, text = _pytest(tmp_path)
    assert code == 0 and '未决结构问题' not in text, text
    code, text = _static(tmp_path)
    assert (code, text) == (0, ''), text
    hold = tmp_path / 'shop/hold.py'
    hold.write_text(hold.read_text().replace("'held'", "'paused'"))
    lead = ('线索：未决结构问题：Job.status 有 3 个文件在写，没有登记负责人：shop/close.py:5  shop/hold.py:5  shop/reopen.py:5'
            ' → 先告诉主人，问谁负责；定下来后在负责的函数旁写 # flowguard: owner Job.status writers=close,hold,reopen'
            '（只留主人认可的写入者），并在 .flowguard/ledger.toml 记下决定：')
    code, text = _pytest(tmp_path)
    assert code == 0 and lead in text, text
    assert '    [structure."writers:Job.status"]' in text, text
    code, text = _static(tmp_path)
    assert code == 0 and lead in text, text
    code, text = _static(tmp_path, '--all')
    assert '1. 写入：Job.status 有 3 个文件在写，没有登记负责人' in text, text


def test_a_comment_above_a_function_with_callbacks_does_not_touch_its_structure_problem(tmp_path):
    def writer(name, status):
        return (f"export async function {name}(prisma: any, ids: string[]) {{\n"
                f"  await Promise.all(ids.map(async (id) => {{\n"
                f"    await prisma.job.update({{ where: {{ id }}, data: {{ status: '{status}' }} }});\n"
                f"  }}));\n}}\n")
    _commit(tmp_path, {
        'prisma/schema.prisma': 'model Job {\n  id     String @id\n  status String\n}\n',
        'src/close.ts': writer('closeJobs', 'closed'), 'src/hold.ts': writer('holdJobs', 'held'),
        'src/reopen.ts': writer('reopenJobs', 'open'),
    })
    hold = tmp_path / 'src/hold.ts'
    hold.write_text('// flowguard: sensor HOLD_JOBS\n' + hold.read_text(encoding='utf-8'), encoding='utf-8')
    code, text = _static(tmp_path)
    assert code == 0 and '未决结构问题' not in text, text      # the callback only moved one line down
    hold.write_text(hold.read_text(encoding='utf-8').replace("'held'", "'paused'"), encoding='utf-8')
    code, text = _static(tmp_path)
    assert code == 0 and '线索：未决结构问题：Job.status 有 3 个文件在写' in text, text      # an edit inside it does


def test_a_structure_decision_closes_its_problem_and_a_decided_owner_needs_its_anchor(tmp_path):
    _commit(tmp_path, WRITERS)
    (tmp_path / 'owner.txt').write_text('Job.status belongs to the close workflow; the other writers must call it.\n')
    code, text = _flowguard(tmp_path, 'req', 'add', str(tmp_path / 'owner.txt'), '--id', 'R1')
    assert code == 0, text
    ledger = tmp_path / '.flowguard/ledger.toml'
    ledger.write_text('[structure."writers:Job.status"]\ndecision = "too short"\nsource = "R1"\n', encoding='utf-8')
    code, text = _static(tmp_path, '--all')
    assert code == 1 and '结构决定 [structure."writers:Job.status"]：decision 至少 8 个词' in text, text
    ledger.write_text('[structure."writers:Job.status"]\ndecision = "close owns the status; hold and reopen will call close later"\n'
                      'source = "R9"\n', encoding='utf-8')
    code, text = _static(tmp_path, '--all')
    assert code == 1 and 'source "R9" 不是已存的主人原话' in text, text
    ledger.write_text('[structure."writers:Job.status"]\ndecision = "close owns the status; hold and reopen will call close later"\n'
                      'source = "R1"\n', encoding='utf-8')
    code, text = _static(tmp_path, '--all')
    assert code == 1, text
    assert ('红：结构决定 [structure."writers:Job.status"] 记下了谁负责，但没有 owner 锚点 → 在负责的函数旁加一行：'
            '# flowguard: owner Job.status writers=close,hold,reopen\n') in text, text
    assert '写入：Job.status' not in text, text               # decided: no longer listed
    close = tmp_path / 'shop/close.py'
    close.write_text('# flowguard: owner Job.status writers=close,hold,reopen\n' + close.read_text())
    code, text = _static(tmp_path, '--all')
    assert code == 0 and '结构决定' not in text and '写入：Job.status' not in text, text


def test_the_session_brief_names_the_heaviest_open_structure_problems_in_one_line(tmp_path):
    _commit(tmp_path, WRITERS)
    code, before = _flowguard(tmp_path)
    assert code == 0, before
    code, text = _static(tmp_path, '--all')
    assert code == 0, text
    code, after = _flowguard(tmp_path)
    assert code == 0 and len(after.splitlines()) - len(before.splitlines()) == 1, (before, after)
    assert after.splitlines()[-1] == ('未决结构问题 0 项（另 1 个字段多处写入、没有负责人），最重：写入 Job.status'
                                      '（上次检查；check --static --all 列出全部和下一步）'), after


# ---- R61: TS old values and unchanged look-alikes ----------------------------------------------------

def test_a_changed_typescript_constant_and_function_lead_to_the_places_left_behind(tmp_path):
    _commit(tmp_path, {
        'src/policy.ts': '''
            export const GRACE_DAYS = 14;
            export function overdue(days: number) {
              return days > GRACE_DAYS;
            }
        ''',
        'src/reminders.ts': '''
            export function remind(days: number) {
              if (days > 14) { return 'late'; }
              return 'fine';
            }
        ''',
        'src/fees.ts': '''
            export function lateFee(days: number, rate: number) {
              const extra = days > 3 ? days - 3 : 0;
              return Math.round(extra * rate * 100) / 100;
            }
        ''',
        'src/legacy/fees.ts': '''
            export function lateCharge(days: number, rate: number) {
              const extra = days > 3 ? days - 3 : 0;
              return Math.round(extra * rate * 100) / 100;
            }
        ''',
    })
    policy = tmp_path / 'src/policy.ts'
    policy.write_text(policy.read_text().replace('= 14', '= 21'))
    fees = tmp_path / 'src/fees.ts'
    fees.write_text(fees.read_text().replace('days > 3 ? days - 3', 'days > 5 ? days - 5'))
    code, text = _static(tmp_path)
    assert code == 0, text
    assert _lines(text, '线索：旧值 14') == [
        '线索：旧值 14 还出现在 1 个判断里：src/reminders.ts:2 → 需求变了就一起改；要锁定它们，在负责人上方写 '
        '# flowguard: owner 名，副本上方写 # flowguard: sensor 名'], text
    alone = next(line for line in _lines(text, '线索：lateFee'))
    assert alone.startswith('线索：lateFee（src/fees.ts:1）改了，改前和它一模一样的 1 份没改：src/legacy/fees.ts:1'), alone
    assert '// flowguard: owner LATEFEE' in alone, alone


# ---- the ledger's TS catch fallbacks and a TS data owner, without pytest -----------------------------

def test_check_static_reports_a_new_typescript_fallback_and_a_write_outside_its_owner(tmp_path):
    _planning(tmp_path)
    _commit(tmp_path, {'backend/src/owners.ts': '// flowguard: owner Employee.organizationalUnitId writers=transferEmployee\nexport {};\n'})
    code, text = _flowguard(tmp_path, 'ledger', 'init')
    assert code == 0, text
    _commit(tmp_path, message='ledger')
    code, text = _static(tmp_path)
    assert (code, text) == (0, ''), text
    _write(tmp_path, {'backend/src/services/rogue.ts': '''
        export async function moveEmployee(prisma: any, id: string, unit: string, next: any) {
          try {
            await prisma.employee.update({ where: { id }, data: { organizationalUnitId: unit } });
          } catch (error) {
            next(error);
          }
          try {
            await prisma.auditEvent.create({ data: { entityId: id } });
          } catch (error) {
            console.warn('audit failed', error);
          }
        }
    '''})
    code, text = _static(tmp_path)
    assert code == 1, text
    assert '红：新增兜底未登记：backend/src/services/rogue.ts:9 catch any 之后能不抛出就结束' in text, text
    assert '    ["backend/src/services/rogue.ts:moveEmployee:any"]' in text and 'rogue.ts:4' not in text, text
    red = next(line for line in text.splitlines() if line.startswith('红：负责人以外新增写入'))
    assert red.startswith('红：负责人以外新增写入 Employee.organizationalUnitId：backend/src/services/rogue.ts:3 moveEmployee（update）'), red
