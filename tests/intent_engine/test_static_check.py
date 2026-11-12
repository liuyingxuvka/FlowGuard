"""`check --static` and the structure health checks (round 20, stage 7b and 5b; fixed examples 16 and 17).

Each project commits its baseline first; only what the working tree adds is reported, and `--all` also
lists every open structure problem. The Planning Tool fragments come from `tests/fixtures/planning_tool`
and `tests/fixtures/planning_tool_static` (sources and line ranges in their READMEs).
"""
from contextlib import closing
import json
import re
import os
from pathlib import Path
import shutil
import subprocess
import sys
import textwrap

import pytest

from tests.intent_engine import _cli_fixture
from tests.intent_engine._cli_fixture import display_text as _text, unchecked

from flowguard.intent import anchors, cache
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


def _block(text, *, everything=False):
    """The lines of the FlowGuard block a run printed after its first line (`_cli_fixture.block`); `everything` (--all)
    has no budget: every line, each of the block's shapes."""
    if not everything:
        return _cli_fixture.block(text)[1:]
    lines = _text(text).splitlines()
    lines = lines[next(index for index, line in enumerate(lines) if re.match(r'FlowGuard \d+\.\d+ \(', line)):]
    lines = lines[:next((index for index, line in enumerate(lines) if line.startswith('deprecated: ')), len(lines))]
    assert all(_cli_fixture.SHAPE.match(line) for line in lines), lines
    return lines[1:]


def _reds(root, text, prefix='red: '):
    """[(line, detail)] of each line of the block in `text` that starts with `prefix`, with the detail `show --last`
    prints under the same line of that run in `root`."""
    shown = _cli_fixture.last(root).splitlines()
    starts = [index for index, line in enumerate(shown) if line.startswith(prefix)]
    lines = [line for line in _block(text, everything=True) if line.startswith(prefix)]
    assert len(starts) == len(lines), (lines, shown)
    return [(line, [said.strip() for said in shown[start + 1:next((index for index, said in enumerate(shown[start + 1:], start + 1)
                                                                  if not said.startswith('    ')), len(shown))]])
            for line, start in zip(lines, starts)]


def _last(root, prefix):
    """[(line, detail)] of the last run's lines in `root` that start with `prefix`, as `show --last` prints them: every
    line uncut, its paths in full, with the detail under it."""
    shown = _cli_fixture.last(root).splitlines()
    return [(line, [said.strip() for said in shown[index + 1:next((later for later, said in enumerate(shown[index + 1:], index + 1)
                                                                  if not said.startswith('    ')), len(shown))]])
            for index, line in enumerate(shown) if line.startswith(prefix)]


def _leads(root):
    """The 5.0-deprecated leads of the last run in `root`, which only `show --last` prints, each `feature: text`."""
    shown = _cli_fixture.last(root).splitlines()
    return [line.strip() for line in shown[shown.index('deprecated leads (5.0):') + 1:]] if 'deprecated leads (5.0):' in shown else []


def _names(root):
    """The finding names of the last run's lines in `root` (`cache.read_last`)."""
    return [line['name'] for line in cache.read_last(_config(root))['lines']]


def _detail(root, line):
    """The detail `show --last` prints under the last run's line that starts with `line` (its paths in full)."""
    shown = _cli_fixture.last(root).splitlines()
    start = next(index for index, said in enumerate(shown) if said.startswith(line))
    return [said.strip() for said in shown[start + 1:next((index for index, said in enumerate(shown[start + 1:], start + 1)
                                                          if not said.startswith('    ')), len(shown))]]


# ---- check --static: only what the change adds; exit 1 on red --------------------------------------

def test_check_static_reports_only_new_values_outside_a_check_and_lists_old_ones_with_all(tmp_path):
    _commit(_planning(tmp_path, 'planning_tool_static'))
    code, text = _static(tmp_path)
    assert code == 0 and _block(text) == [], text            # nothing changed: the first line alone
    code, text = _static(tmp_path, '--all')
    assert code == 0, text
    old = next(line for line in _block(text, everything=True) if line.startswith('before: values '))
    assert old == ('before: values AuditEvent.severity at authority-integrity-repair.service.ts:repairOrganizationAuthority was broken '
                   'at task start -> leave it unless your task is about it'), old
    _write(tmp_path, {'backend/src/services/notice.service.ts': '''
        export async function notice(prisma: any, id: string) {
          await prisma.auditEvent.create({ data: { severity: 'WARNING', entityId: id } });
          await prisma.auditEvent.create({ data: { severity: id ? 'NOTICE' : 'INFO', entityId: id } });
        }
    '''})
    code, text = _static(tmp_path)
    assert code == 1, text
    red = _lines(text, 'red: ')
    assert red == ["red: values AuditEvent.severity: notice.service.ts:notice writes 'NOTICE' outside 'INFO'|'WARNING'|'ERROR'|'CRITICAL' "
                   '-> use a declared value'], text
    assert _detail(tmp_path, 'red: values AuditEvent.severity: ') == [
        'declared at CHECK backend/prisma/migrations/20260910120000_align_runtime_storage_contract/migration.sql:9']
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
    title = rf'FlowGuard \d+\.\d+ \(since {{}}\): 1 red, 1 impact; \d+\.\d s'
    assert code == 1 and re.fullmatch(title.format('--base HEAD'), text.splitlines()[0]), text      # the option the CLI took
    code, text = _static(tmp_path)
    assert code == 1 and re.fullmatch(title.format(head[:7]), text.splitlines()[0]), text


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
        red = _lines(text, 'red: values ')
        assert code == 1 and red == ["red: values Item.kind: items.ts:add writes 'C' outside 'A'|'B' -> use a declared value"], text
        # the files that spell the enum alike share one set, which names each of them
        assert _detail(root, 'red: values Item.kind: ') == ['declared at enum Kind (' + ', '.join(f'{file}:1' for file in sorted(files))
                                                           + ', generator schema not found; checked against all schemas in this package)']
    # prisma.config.ts names the schema in use: the template beside it only describes, and nothing is guessed
    root = tmp_path / 'config'
    _commit(root, {'prisma/schema.sqlite.prisma': schema.replace('  B\n', '  B\n          C\n'),
                   'prisma/schema.postgres.prisma': schema,
                   'prisma.config.ts': "import { defineConfig } from 'prisma/config';\n"
                                       "export default defineConfig({ schema: 'prisma/schema.postgres.prisma' });\n"})
    _write(root, write)
    code, text = _static(root)
    red = _lines(text, 'red: values ')
    assert code == 1 and red == ["red: values Item.kind: items.ts:add writes 'C' outside 'A'|'B' -> use a declared value"], text
    assert _detail(root, 'red: values Item.kind: ') == ['declared at enum Kind (prisma/schema.postgres.prisma:1)']


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
    guessed = ', generator schema not found; checked against all schemas in this package'
    postgres, sqlite = (f'enum Tone (admin/prisma/schema.{name}.prisma:11{guessed})' for name in ('postgres', 'sqlite'))
    assert code == 1 and _reds(tmp_path, text) == [
        ("red: values Note.tone: notes.ts:note writes 'Z' outside 'X'|'Y' -> use a declared value", [f'declared at {postgres}']),
        ("red: values Note.tone: notes.ts:note writes 'Y', 'Z' outside 'X' -> use a declared value", [f'declared at {sqlite}'])], text
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
    assert code == 1 and _reds(tmp_path, text) == [
        ("red: values Item.kind: items.ts:add writes 'C' outside 'A'|'B' -> use a declared value",
         ['declared at enum Kind (prisma/main.prisma:1, generator schema not found; checked against all schemas in this package)'])], text
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
    guessed = ', generator schema not found; checked against all schemas in this package'
    admin, web = f'enum Tone (admin/prisma/schema.postgres.prisma:1{guessed})', f'enum Tone (web/prisma/schema.sqlite.prisma:1{guessed})'
    assert code == 1 and _reds(tmp_path, text) == [
        ("red: values Note.tone: a.ts:note writes 'Z' outside 'X'|'Y' -> use a declared value", [f'declared at {admin}']),
        ("red: values Note.tone: seed.ts:note writes 'W' outside 'X'|'Y' -> use a declared value", [f'declared at {admin}']),
        ("red: values Note.tone: seed.ts:note writes 'W' outside 'X'|'Z' -> use a declared value", [f'declared at {web}'])], text


def test_guessed_templates_with_the_same_enum_share_one_set_that_names_every_file(tmp_path):
    # 4.2 review: three provider templates with one enum repeated the same red segment and the same problem
    # three times, so `--all` and the brief counted it three times.
    _commit(tmp_path, {'prisma/schema.sqlite.prisma': _tone_schema('X', 'Y'), 'prisma/schema.postgres.prisma': _tone_schema('X', 'Y'),
                       'prisma/schema.sqlserver.prisma': _tone_schema('X', 'Y'), 'prisma/schema.mysql.prisma': _tone_schema('X')})
    _write(tmp_path, {'src/notes.ts': _tone_writes('Y', 'Z')})
    code, text = _static(tmp_path)
    guessed = ', generator schema not found; checked against all schemas in this package'
    one = f'enum Tone (prisma/schema.mysql.prisma:1{guessed})'
    three = f'enum Tone (prisma/schema.postgres.prisma:1, prisma/schema.sqlite.prisma:1, prisma/schema.sqlserver.prisma:1{guessed})'
    assert code == 1 and _reds(tmp_path, text) == [
        ("red: values Note.tone: notes.ts:note writes 'Y', 'Z' outside 'X' -> use a declared value", [f'declared at {one}']),
        ("red: values Note.tone: notes.ts:note writes 'Z' outside 'X'|'Y' -> use a declared value", [f'declared at {three}'])], text
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
    lines = ['before: values Account.status at a.ts:add was broken at task start -> leave it unless your task is about it',
             'before: values Note.tone at n.ts:2 was broken at task start -> leave it unless your task is about it']
    assert code == 0 and [line for line in _block(text, everything=True) if line.startswith('before: values ')] == lines, text
    assert _detail(tmp_path, 'before: values Account.status ') == ['declared at CHECK prisma/migrations/002/migration.sql:2']
    assert cache.structure_summary(_config(tmp_path))['count'] == 3
    # a folder is named by its name and '/', as a file by its name
    assert ('before: columns migrations/ against prisma/schema.prisma at migrations/ was broken at task start -> leave it unless your task '
            'is about it') in _block(text, everything=True), text
    # the decision a 4.1 project recorded on that field still closes it (its problem leaves the open ones); a
    # finding that can be red keeps its line (design 4.7: only act = "ignore" of known.toml hides a line)
    sentence = 'Old accounts keep the status gone until the cleanup job removes them.'
    _write(tmp_path, {'docs/decisions.md': sentence + '\n', '.flowguard/ledger.toml': (
        '[structure."values:Account.status"]\ndecision = "old accounts keep the status gone until the cleanup job removes them"\n'
        f'source = {{ file = "docs/decisions.md", text = "{sentence}" }}\n')})
    code, text = _static(tmp_path, '--all')
    assert code == 0 and [line for line in _block(text, everything=True) if line.startswith('before: values ')] == lines, text
    assert _detail(tmp_path, 'before: values Note.tone ') == ['declared at web/types.ts:1']
    assert cache.structure_summary(_config(tmp_path))['count'] == 2
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
    assert code == 1 and _reds(tmp_path, text) == [
        ("red: values Person.role: b.ts:2 writes 'N2' outside 'X'|'Y' -> use a declared value", [f'declared at {tier}']),
        ("red: values User.role: a.ts:2 writes 'N1' outside 'A'|'B' -> use a declared value", [f'declared at {role}']),
        ("red: values User.role: c.ts:2 writes 'N3' outside 'A'|'B' -> use a declared value", [f'declared at {role}'])], text


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
    assert code == 1 and _reds(tmp_path, text) == [
        ("red: values Item.kind: sample.ts:2 writes 'C' outside 'A'|'B' -> use a declared value",
         ['declared at enum Kind (prisma/schema.prisma:1)'])], text


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
    # 'C' at a.ts:3 is db2's own value
    assert code == 1 and _reds(root, text) == [
        ("red: values User.role: a.ts:5 writes 'C' outside 'A'|'B' -> use a declared value",
         ['declared at enum Role (backend/prisma/db1/schema.prisma:6)']),
        ("red: values User.role: a.ts:4 writes 'B' outside 'A'|'C' -> use a declared value",
         ['declared at enum Role (backend/prisma/db2/schema.prisma:6)'])], text
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
    # api defines no Note: a set still judges it; web defines Note itself and is not judged by db
    assert code == 1 and _reds(root, text) == [("red: values Note.tone: a.ts:add writes 'Q' outside 'X'|'Z' -> use a declared value",
                                                ['declared at enum Tone (web/prisma/schema.prisma:1)'])], text
    assert _detail(root, "red: values Note.tone: api/src/a.ts:add ") == ['declared at enum Tone (web/prisma/schema.prisma:1)']


def _role_schema(values, output=None, source=None):
    """A schema of `User.role`, typed by `enum Role` of these values, or `String` when `values` is None."""
    return ((f'datasource db {{\n  provider = "{source}"\n  url      = env("DATABASE_URL")\n}}\n\n' if source else '')
            + (f'generator client {{\n  provider = "prisma-client-js"\n  output   = "{output}"\n}}\n\n' if output else '')
            + ('model User {\n  id   String @id\n  role String\n}\n' if values is None else
               'enum Role {\n' + ''.join(f'  {value}\n' for value in values) + '}\n\nmodel User {\n  id   String @id\n  role Role\n}\n'))


def _red_values(root, text):
    """Each value red of the last run in `root` as `show --last` prints it, paths in full: `Model.field: place writes
    values outside allowed (where they are declared)`, without its step; the block in `text` has as many."""
    shown, step, out = _cli_fixture.last(root).splitlines(), ' -> use a declared value', []
    for index, line in enumerate(shown):
        if line.startswith('red: values '):
            assert line.endswith(step), line
            declared = [said.strip().removeprefix('declared at ') for said in shown[index + 1:index + 2] if said.startswith('    declared at ')]
            out.append(line[len('red: values '):-len(step)] + ''.join(f' ({where})' for where in declared))
    assert len(out) == len(_lines(text, 'red: values ')), (out, text)
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
        line = 1 if name == 'reporting' else 6
        assert code == 1 and _red_values(root, text) == [
            f"User.role: src/w.ts:5 writes 'Z' outside 'A'|'B' (enum Role (prisma/schema.prisma:{line}))",
            f"User.role: src/w.ts:add writes 'Z' outside 'A'|'B' (enum Role (prisma/schema.prisma:{line}))"], (name, text)


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
    assert code == 1 and _red_values(tmp_path, text) == [
        "Grid.granularity: src/page.ts:2 writes 'MONTHLY' outside 'WEEK'|'MONTH' (Granularity (src/types/units.ts:1))"], text


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
        assert code == 1 and _red_values(root, text) == [
            "Account.status: src/a.ts:add writes 'gone' outside 'open'|'closed' (CHECK prisma/migrations/001/migration.sql:1)",
            "User.role: src/a.ts:add writes 'C' outside 'A'|'B' (enum Role (prisma/schema/enums.prisma:1))"], (name, text)


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
    assert code == 1 and _red_values(tmp_path, text) == [
        "User.role: apps/api/src/a.ts:add writes 'C' outside 'A'|'B' (enum Role (apps/api/prisma/schema.prisma:1))",
        "User.role: scripts/seed.ts:add writes 'C' outside 'A'|'B' (enum Role (apps/api/prisma/schema.prisma:1))",
        "User.role: apps/worker/src/bad.ts:add writes 'B' outside 'A'|'C' (enum Role (apps/worker/prisma/schema.prisma:1))"], text


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
    assert code == 1 and _red_values(tmp_path, text) == [
        "User.role: backend/src/a.ts:9 writes 'B' outside 'A'|'C' (enum Role (backend/prisma/db2/schema.prisma:6))"], text


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
    assert code == 1 and _red_values(tmp_path, text) == [
        "User.role: src/a.ts:5 writes 'B' outside 'A'|'C' (enum Role (prisma/analytics/schema.prisma:6))",
        "User.role: src/a.ts:4 writes 'C' outside 'A'|'B' (enum Role (prisma/schema.prisma:6))"], text


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
    assert code == 1 and _red_values(tmp_path, text) == [
        "Props.tone: src/Tile.tsx:1 writes 'sunk' outside 'flat'|'raised' (src/Card.tsx:1)",
        "Props.variant: src/Panel.tsx:2 writes 'primary' outside 'info'|'warning' (src/Badge.tsx:1)",
        "Props.variant: src/Button.tsx:3 writes 'info' outside 'primary'|'secondary' (src/Button.tsx:1)"], text
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
    assert code == 1 and _red_values(root, text) == [
        "User.role: apps/api/src/a.ts:add writes 'Z' outside 'A'|'B' (enum Role (apps/api/prisma/schema.prisma:1))",
        "User.role: scripts/seed.ts:add writes 'Z' outside 'A'|'B' (enum Role (apps/api/prisma/schema.prisma:1))"], text
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
    assert code == 1 and _red_values(root, text) == [
        "User.role: backend/src/a.ts:4 writes 'Z' outside 'A'|'B' (enum Role (backend/prisma/db1/schema.prisma:6))"], text


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
    assert code == 1 and _red_values(tmp_path, text) == [
        "Props.variant: src/Loose.tsx:1 writes 'other' outside 'info'|'warning' (src/Badge.tsx:1)",
        "Props.variant: src/Panel.tsx:2 writes 'error' outside 'info'|'warning' (src/Badge.tsx:1)"], text


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
    # the decision closes Link's problem alone (the open problems drop by one); a finding that can be red keeps its line
    assert code == 0 and [line for line in _block(text, everything=True) if line.startswith('before: values ')] == [
        f'before: values Props.variant at {name}.tsx:3 was broken at task start -> leave it unless your task is about it'
        for name in ('Badge', 'Button', 'Link')], text
    assert [_detail(tmp_path, f'before: values Props.variant at src/{name}.tsx:3 ') for name in ('Badge', 'Button', 'Link')] == [
        ['declared at BadgeVariant (src/variants.ts:1)'], ['declared at ButtonVariant (src/variants.ts:2)'],
        ['declared at LinkVariant (src/variants.ts:3)']]
    assert cache.structure_summary(_config(tmp_path))['count'] == 2


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
    # the 4.1 decision closes the enum's problem, as in 4.1 (the open problems are the CHECK's, which 4.1 did not read
    # beside it, and the declarations that differ); a finding that can be red keeps its line
    assert code == 0 and _block(text, everything=True)[:2] == [
        'before: values Account.status at a.ts:add was broken at task start -> leave it unless your task is about it'] * 2, text
    shown = _cli_fixture.last(tmp_path).splitlines()
    assert [shown[index + 1].strip() for index, line in enumerate(shown) if line.startswith('before: values ')] == [
        'declared at CHECK prisma/migrations/001/migration.sql:1',
        'declared at enum Status (prisma/schema.postgres.prisma:6, generator schema not found; checked against all schemas in this package)']
    assert cache.structure_summary(_config(tmp_path))['count'] == 1


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
    assert found == [('columns:./~db/schema.prisma', 'missing columns ./'), ('ondelete:./~db/schema.prisma', 'onDelete ./')], found


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
    # --leads (deprecated) lists every line without the budget; the release snapshot keeps prisma/ in the live path
    assert code == 0 and _block(text) == [
        "impact: declarations Item.kind: prisma/schema.prisma:1 declares 'A' | 'B' | 'C' | 'D'; src/kinds.ts:2 declares 'A' | 'B' | 'C' "
        '-> fix it, or say why in your report'], text
    assert 'deprecated: check --leads goes in 5.0 -> write python -m flowguard show --last' in text.splitlines(), text


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
    assert code == 1 and _red_values(tmp_path, text) == [
        "Item.kind: src/alias.ts:2 writes 'C' outside 'A'|'B' (enum Kind (prisma/schema.prisma:6))",
        "Item.kind: src/output.ts:2 writes 'G' outside 'A'|'B' (enum Kind (prisma/schema.prisma:6))",
        "Item.kind: src/space.ts:3 writes 'D', 'E' outside 'A'|'B' (enum Kind (prisma/schema.prisma:6))"], text


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
    # 'UPDATED' is in the CHECK the database runs (the template enum lacks it); the archived description under
    # docs/ does not add 'ARCHIVED'; 'MID' passes the CHECK but not the enum of the schema in use; the frontend
    # Demand is judged by its own union only. Every one was there at the task start: before, with --all.
    assert code == 0 and _block(text, everything=True) == [
        f'before: {subject} at {place} was broken at task start -> leave it unless your task is about it' for subject, place in (
            ('values Gauge.level', 'notice.service.ts:notify'), ('values Notice.kind', 'notice.service.ts:notify'),
            ('values Demand.unit', 'demand.ts:3'), ('declarations Gauge.level', 'central.prisma:6'),
            ('declarations Notice.kind', 'migration.sql:1'))], text
    shown = _cli_fixture.last(tmp_path).splitlines()
    assert [shown[index + 1].strip() for index, line in enumerate(shown) if line.startswith('before: values ')] == [
        'declared at enum Level (backend/prisma/central/central.prisma:6)', 'declared at CHECK backend/prisma/migrations/001/migration.sql:1',
        'declared at frontend/src/types.ts:1'], shown


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
    assert code == 0 and _block(text) == [], text            # move writes Local.unitId through this.mirror()
    _write(tmp_path, {'src/admin.ts': '''
        export async function editCentral(prisma: any, id: string, unit: string) {
          await prisma.central.update({ where: { id }, data: { orgUnitId: unit } });
        }
    '''})
    code, text = _static(tmp_path)
    assert code == 1, text
    assert _reds(tmp_path, text) == [
        ('red: together Central.orgUnitId: admin.ts:editCentral writes Central.orgUnitId without Local.unitId '
         '-> also write Local.unitId in editCentral', ['JS/TS calls resolved by name'])], text


# Round 22 E1, hole 1: the four `w1` wrong fixes of the Planning Tool's registered pairs write the partner field as
# `undefined`, which Prisma leaves as it is. Each passed check --static as if the partner were written.
E1_SCHEMA = '''
    model CentralEmployee {
      id        String @id
      orgUnitId String
    }

    model Employee {
      id                   String @id
      sapReference         String
      organizationalUnitId String?
    }

    model Project {
      id       String @id
      leaderId String
    }

    model ProjectMember {
      id         String @id
      projectId  String
      employeeId String
      role       String
    }

    model CentralOrgUnit {
      id                String @id
      managerEmployeeId String?
      managerSapNumber  String?
    }

    model PspElement {
      id             Int  @id
      parentPspId    Int?
      hierarchyLevel Int
    }
'''
E1_OWNERS = ('// flowguard: owner CentralEmployee.orgUnitId with=Employee.organizationalUnitId\n'
             '// flowguard: owner Project.leaderId with=ProjectMember.*\n'
             '// flowguard: owner CentralOrgUnit.managerEmployeeId with=CentralOrgUnit.managerSapNumber\n'
             '// flowguard: owner PspElement.parentPspId with=PspElement.hierarchyLevel\nexport {};\n')
E1_WRONG_FIXES = {
    'CentralEmployee.orgUnitId': '''
        export async function reassignHomeUnit(prisma: any, id: string, orgUnitId: string) {
          await prisma.centralEmployee.update({ where: { id }, data: { orgUnitId } });
          await prisma.employee.updateMany({ where: { sapReference: id }, data: { organizationalUnitId: undefined } });
        }
    ''',
    'Project.leaderId': '''
        export async function changeProjectLeader(prisma: any, projectId: string, employeeId: string) {
          return prisma.$transaction(async (tx: any) => {
            await tx.projectMember.updateMany({ where: { projectId, employeeId }, data: { role: undefined } });
            await tx.project.update({ where: { id: projectId }, data: { leaderId: employeeId } });
          });
        }
    ''',
    'CentralOrgUnit.managerEmployeeId': '''
        export async function setUnitManager(prisma: any, orgUnitId: string, employeeId: string) {
          await prisma.centralOrgUnit.update({
            where: { id: orgUnitId },
            data: { managerEmployeeId: employeeId, managerSapNumber: undefined },
          });
        }
    ''',
    'PspElement.parentPspId': '''
        export async function reparentLeafElement(prisma: any, elementId: number, newParentId: number) {
          await prisma.pspElement.update({
            where: { id: elementId },
            data: { parentPspId: newParentId, hierarchyLevel: undefined },
          });
        }
    ''',
}
# Prisma's `{ set: undefined }` leaves the field as it is too, and so does undefined as the operand of the four
# number operations (round 22 E1 review: `{ increment: undefined }`, `void 0` and `data.x = undefined` were writes).
for op in ('set', 'increment', 'decrement', 'multiply', 'divide'):
    E1_WRONG_FIXES[f'PspElement.parentPspId {{ {op} }}'] = E1_WRONG_FIXES['PspElement.parentPspId'].replace(
        'hierarchyLevel: undefined', f'hierarchyLevel: {{ {op}: undefined }}')
E1_WRONG_FIXES['PspElement.parentPspId void'] = E1_WRONG_FIXES['PspElement.parentPspId'].replace('undefined', 'void 0')
E1_WRONG_FIXES['PspElement.parentPspId member'] = '''
        export async function reparentLeafElement(prisma: any, elementId: number, newParentId: number) {
          const data: any = { parentPspId: newParentId };
          data.hierarchyLevel = undefined;
          await prisma.pspElement.update({ where: { id: elementId }, data });
        }
    '''


@pytest.mark.parametrize('case', sorted(E1_WRONG_FIXES))
def test_a_partner_field_written_as_undefined_is_not_written(tmp_path, case):
    owner = case.partition(' ')[0]
    _commit(tmp_path, {'prisma/schema.prisma': E1_SCHEMA, 'src/owners.ts': E1_OWNERS})
    _write(tmp_path, {'src/change.ts': E1_WRONG_FIXES[case]})
    code, text = _static(tmp_path)
    red = _lines(text, 'red: ')
    assert code == 1 and len(red) == 1 and red[0].startswith(f'red: together {owner}: change.ts:'), text
    # null is a value Prisma writes: the same change with null holds the pair.
    _write(tmp_path, {'src/change.ts': E1_WRONG_FIXES[case].replace('undefined', 'null').replace('void 0', 'null')})
    code, text = _static(tmp_path)
    assert code == 0 and not _lines(text, 'red: '), text


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
    assert code == 1 and _lines(text, 'red: ') == [
        'red: together Central.orgUnitId: admin.ts:editCentral writes Central.orgUnitId without Local.unitId -> also write Local.unitId in editCentral',
        'red: together Project.leaderId: admin.ts:lead writes Project.leaderId without Member.* -> also write Member in lead'], text


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
    assert code == 0 and 'missing paired write' not in text, text
    _write(tmp_path, {'src/admin.ts': '''
        export async function editCentral(prisma: any, id: string, unit: string) {
          await prisma.central.update({ where: { id }, data: { orgUnitId: unit } });
        }
    '''})
    code, text = _pytest(tmp_path)
    assert code == 1, text
    assert ('red: together Central.orgUnitId: admin.ts:editCentral writes Central.orgUnitId without Local.unitId '
            '-> also write Local.unitId in editCentral') in text.splitlines(), text
    shown = _cli_fixture.last(tmp_path).splitlines()          # the red line in full, its detail under it
    red = shown.index('red: together Central.orgUnitId: src/admin.ts:editCentral writes Central.orgUnitId without '
                      'Local.unitId -> also write Local.unitId in editCentral')
    assert shown[red + 1] == '    JS/TS calls resolved by name', shown


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
    assert code == 1 and _red_values(tmp_path, text) == [
        "Project.sourceType: src/projects.ts:create writes 'CSV_IMPORT' outside 'MANUAL'|'IMPORT' (CHECK prisma/migrations/001/migration.sql:1)"], text


def test_a_pair_limited_to_updates_does_not_hold_the_writes_that_make_a_row(tmp_path):
    # Planning Tool 0.6.28 (round 21, V4): the business references follow a SAP number when it changes; with
    # with= alone every function that creates an employee was red.
    owner = '// flowguard: owner Employee.sapRef with=Opportunity.responsibleNo on=update\nexport {};\n'
    # The agreement holds at the baseline; the functions are this change's (a new agreement over old code is judged
    # against the baseline code: what it finds there was there before the change).
    _commit(tmp_path, {
        'src/owners.ts': owner,
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
    })
    _write(tmp_path, {
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
    code, text = _static(tmp_path)
    assert code == 1, text
    assert _lines(text, 'red: ') == ['red: together Employee.sapRef: employees.ts:fixNumber writes Employee.sapRef without '
                                     'Opportunity.responsibleNo (updates only) -> also write Opportunity.responsibleNo in fixNumber'], text
    _write(tmp_path, {'src/owners.ts': owner.replace('on=update', 'on=create')})
    code, text = _static(tmp_path)
    assert code == 1 and _lines(text, 'red: ') == ['red: together Employee.sapRef: employees.ts:hire writes Employee.sapRef without '
                                                   'Opportunity.responsibleNo (creates only) -> also write Opportunity.responsibleNo in hire'], text
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
    assert _lines(text, 'red: ') == [
        'red: together hires.reserved: store.py:release writes hires.reserved without hires.state=held -> also write hires.state=held in release'], text


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
    # The agreement holds at the baseline; the service is this change's (a new agreement over old code is judged
    # against the baseline code).
    _commit(tmp_path, {
        'backend/src/owners.ts': '// flowguard: owner Unit.managerId with=Unit.managerSap\nexport {};\n',
        'backend/package.json': '{"name": "backend"}\n',
        'frontend/package.json': '{"name": "frontend"}\n',
        'backend/prisma/schema.prisma': '''
            model Unit {
              id         String  @id
              managerId  String?
              managerSap Int?
            }
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
    _write(tmp_path, {
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
    })
    code, text = _static(tmp_path)
    assert code == 1, text
    # moveManager reaches mirrorSap through `this` in its own package; the page's calls are the frontend's own
    # names, and the test that calls dropManager is not part of its operation; the test's fixture is no write to hold.
    assert _lines(text, 'red: ') == [
        f'red: together Unit.managerId: unit.service.ts:{name} writes Unit.managerId without Unit.managerSap -> also write Unit.managerSap in {name}'
        for name in ('removeManager', 'dropManager')], text


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
        'src/nodes.ts:8 move -> if the owner says they change together: // flowguard: together Node.parentId Node.level',
        'with= candidate (reference only): Node.title is written by 2 of the 3 functions that write Node.parentId; not by '
        'src/nodes.ts:8 move -> if the owner says they change together: // flowguard: together Node.parentId Node.title'], text


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
    deletes = _last(tmp_path, 'impact: delete ')
    assert len(deletes) == 1 and len(_lines(text, 'impact: delete ')) == 1, text
    line, detail = deletes[0]
    assert line.startswith('impact: delete Employee: backend/src/services/hard-delete.service.ts:removeEmployeeRow deletes Employee; '
                           'NoAction child tables '), line
    assert detail == ['delete at backend/src/services/hard-delete.service.ts:9  backend/src/services/hard-delete.service.ts:10'], detail
    listed = line.partition('NoAction child tables ')[2].partition(' are not ')[0]
    # deleted (UserRole), counted inside OR (AuthorityAssignment), nulled (AuditEvent), Cascade (EmployeeLog) and a
    # table no code creates or updates rows in (EmployeeBadge) are not listed; the optional self relation
    # Employee.supervisor is (round 21, P12): one employee row is deleted and the copied create writes supervisorId.
    assert listed == 'Employee, EmployeeNote, EmployeeTransfer (3 foreign keys: decidedById, employeeId, requestedById), Notification', listed
    assert 'delete:backend/src/services/hard-delete.service.ts:removeEmployeeRow:Employee' in _names(tmp_path), _names(tmp_path)


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
    assert code == 0 and _lines(text, 'impact: delete ') == [
        'impact: delete Unit: remove.ts:removeUnit deletes Unit; Restrict child tables Room are not deleted, cleared or counted in the same '
        'operation (calls resolved by name) -> fix it, or say why in your report'], text
    assert _detail(tmp_path, 'impact: delete Unit: ') == ['delete at src/remove.ts:2']


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
    assert _lines(text, 'impact: delete ') == [
        'impact: delete Demand: remove.ts:removeDemand deletes Demand; NoAction child tables Demand are not deleted, cleared or counted in the '
        'same operation (calls resolved by name) -> fix it, or say why in your report'], text
    assert _detail(tmp_path, 'impact: delete Demand: ') == ['delete at src/remove.ts:2']


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
    assert code == 0 and _last(tmp_path, 'impact: delete ') == [
        ('impact: delete Node: src/clear.ts:removeNode deletes Node; Restrict child tables Node (2 foreign keys: tenantId, parentId) are not '
         'deleted, cleared or counted in the same operation (calls resolved by name) -> fix it, or say why in your report',
         ['delete at src/clear.ts:5'])], text
    assert len(_lines(text, 'impact: delete ')) == 1, text


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
    # Level rows come from a migration's INSERT, Note rows from code; a test fixture and an archived SQL file
    # under docs/ make no rows the application has.
    before = 'before: uncreated {} at deputies.ts:{} was broken at task start -> leave it unless your task is about it'
    assert code == 0 and _block(text, everything=True) == [
        before.format('Deputy', 'deputiesOf'), before.format('Deputy', 'purge'), before.format('Request', 'purge')], text
    assert {'uncreated:Deputy', 'uncreated:Request'} == set(_names(tmp_path)), _names(tmp_path)
    source = tmp_path / 'src/deputies.ts'
    source.write_text(source.read_text().replace('where: { id } }', 'where: { id }, take: 5 }'))
    code, text = _static(tmp_path)
    # the change touches deputiesOf, which reads Deputy: the problem was there before
    assert code == 0 and _block(text) == [before.format('Deputy', 'deputiesOf')], text


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
    assert code == 0 and _block(text, everything=True) == [
        'before: uncreated Audit at users.ts:add was broken at task start -> leave it unless your task is about it'], text


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
    assert code == 0 and _block(text, everything=True) == [], text
    _write(tmp_path, {'prisma/schema.sqlite.prisma': schema % ('sqlite', 'Cascade')})
    code, text = _static(tmp_path)
    impact = ('impact: onDelete schema.sqlite.prisma against prisma/schema.prisma: schema.sqlite.prisma differs on 1 relations from '
              'prisma/schema.prisma, 1 added in this change: Room.unit (NoAction/Restrict / Cascade) -> fix it, or say why in your report')
    assert code == 0 and _block(text) == [impact], text
    assert _detail(tmp_path, 'impact: onDelete ') == [
        'parentheses show the rule of prisma/schema.prisma first, then that of prisma/schema.sqlite.prisma']
    assert _names(tmp_path) == ['ondelete:prisma/schema.prisma~prisma/schema.sqlite.prisma'], _names(tmp_path)
    code, text = _static(tmp_path, '--all')
    assert code == 0 and _block(text, everything=True) == [impact], text


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
    impact = ('impact: onDelete schema.sqlite.prisma against prisma/schema.prisma: schema.sqlite.prisma differs on 8 relations from '
              'prisma/schema.prisma, 1 added in this change: Zulu.unit (NoAction/Restrict / SetNull) -> fix it, or say why in your report')
    assert code == 0 and _block(text) == [impact], text
    # --all lists the same finding: the change added it, so it is impact, not before
    code, text = _static(tmp_path, '--all')
    assert code == 0 and _block(text, everything=True) == [impact], text


def test_an_ondelete_pair_keeps_its_name_and_its_decision_when_the_other_schema_becomes_the_larger(tmp_path):
    # Round 23 review: the pair is read against the larger of two schemas in use; tables added to the smaller
    # one turned the pair round, renamed the problem and voided the owner's decision.
    a = _rooms('sqlserver', [('Room', 'NoAction')], 'model Hall {\n  id String @id\n}\n')
    b = _rooms('sqlserver', [('Room', 'Cascade')])
    _commit(tmp_path, {'prisma/a.prisma': a, 'prisma/b.prisma': b})
    code, text = _static(tmp_path, '--all')
    assert 'before: onDelete b.prisma against prisma/a.prisma at b.prisma was broken at task start -> leave it unless your task is about it' \
        in _block(text, everything=True), text
    assert 'ondelete:prisma/a.prisma~prisma/b.prisma' in _names(tmp_path), _names(tmp_path)
    name = '[structure."ondelete:prisma/a.prisma~prisma/b.prisma"]'
    _write(tmp_path, {'prisma/b.prisma': b + 'model Shed {\n  id String @id\n}\n\nmodel Barn {\n  id String @id\n}\n'})
    turned = 'before: onDelete a.prisma against prisma/b.prisma at a.prisma was broken at task start -> leave it unless your task is about it'
    code, text = _static(tmp_path, '--all')
    assert turned in _block(text, everything=True), text
    assert 'ondelete:prisma/a.prisma~prisma/b.prisma' in _names(tmp_path), _names(tmp_path)
    code, text = _static(tmp_path)
    # the change added no difference: the pair is before, as the change touches one of its schemas
    assert _block(text) == [turned, 'impact: columns a.prisma against prisma/b.prisma: a.prisma lacks missing table Barn; missing table Shed '
                                    '-> fix it, or say why in your report'], text
    _write(tmp_path, {'docs/decisions.md': 'The SQL Server schema keeps NoAction because of multiple cascade paths.\n',
                      '.flowguard/ledger.toml': name + '\ndecision = "the second schema cascades on purpose, the owner keeps both"\n'
                      'source = { file = "docs/decisions.md", text = "The SQL Server schema keeps NoAction because of multiple cascade paths." }\n'})
    code, text = _static(tmp_path, '--all')
    assert code == 0 and not [line for line in _block(text, everything=True) if 'onDelete ' in line], text


def test_a_change_to_either_schema_of_an_open_ondelete_pair_gets_the_touched_lead(tmp_path):
    _commit(tmp_path, {'prisma/schema.prisma': _rooms('sqlserver', [('Room', 'NoAction')]),
                       'prisma/schema.sqlite.prisma': _rooms('sqlite', [('Room', 'Cascade')])})
    for file in ('prisma/schema.sqlite.prisma', 'prisma/schema.prisma'):
        path = tmp_path / file
        saved = path.read_text(encoding='utf-8')
        path.write_text(saved + '// reviewed\n', encoding='utf-8')
        code, text = _static(tmp_path)
        assert code == 0 and _block(text) == [
            'before: onDelete schema.sqlite.prisma against prisma/schema.prisma at schema.sqlite.prisma was broken at task start -> leave it unless your task is about it'], (file, text)
        assert _detail(tmp_path, 'before: onDelete ') == ['parentheses show the rule of prisma/schema.prisma first, then that of prisma/schema.sqlite.prisma']
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
    assert code == 0 and [line for line in _block(text) if 'onDelete' in line] == [
        'before: onDelete schema.sqlite.prisma against prisma/schema.prisma at schema.sqlite.prisma was broken at task start -> leave it unless your task is about it'], text


def test_a_schema_that_drops_a_relation_but_keeps_its_key_column_has_no_foreign_key(tmp_path):
    # Round 23 check: the side without the foreign key was shown by no test; its table, key column and parent
    # stay, so deleting a Unit there leaves the rooms pointing nowhere.
    _commit(tmp_path, {'prisma/schema.prisma': _rooms('sqlserver', [('Room', 'NoAction')]),
                       'prisma/schema.sqlite.prisma': _rooms('sqlite', [('Room', 'NoAction')])})
    template = _rooms('sqlite', [('Room', 'NoAction')]).replace(
        '  unit   Unit   @relation(fields: [unitId], references: [id], onDelete: NoAction)\n', '').replace('rooms Room[]', '')
    _write(tmp_path, {'prisma/schema.sqlite.prisma': template})
    code, text = _static(tmp_path)
    impact = ('impact: onDelete prisma/schema.sqlite.prisma against prisma/schema.prisma: prisma/schema.sqlite.prisma differs on 1 relations '
              'from prisma/schema.prisma, 1 added in this change: Room.unit (NoAction/Restrict / no foreign key) -> fix it, or say why in your report')
    assert code == 0 and [line for line, _ in _last(tmp_path, 'impact: ')] == [impact] and len(_block(text)) == 1, text
    code, text = _static(tmp_path, '--all')
    # the table and its key column are there: no columns finding
    assert code == 0 and [line for line, _ in _last(tmp_path, '')[1:] if line.startswith(('before: ', 'impact: '))] == [impact], text


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
                'Delete leaves child rows', 'delete:src/remove.ts:removeUnit:Unit'),
    'columns': ({'prisma/schema.prisma': UNITS % ('sqlserver', ''), 'prisma/schema.sqlite.prisma': UNITS % ('sqlite', '')},
                {'prisma/schema.prisma': UNITS % ('sqlserver', '\n      code String')},
                'Columns missing between descriptions', 'columns:prisma/schema.sqlite.prisma~prisma/schema.prisma'),
    'ondelete': ({'prisma/schema.prisma': _rooms('sqlserver', [('Room', 'NoAction')]),
                  'prisma/schema.sqlite.prisma': _rooms('sqlite', [('Room', 'NoAction')])},
                 {'prisma/schema.sqlite.prisma': _rooms('sqlite', [('Room', 'Cascade')])},
                 'onDelete differs', 'ondelete:prisma/schema.prisma~prisma/schema.sqlite.prisma'),
    'labels': ({'src/a.ts': LABELS % ('TYPE_LABELS', 'Area'), 'src/b.ts': LABELS % ('KIND_LABELS', 'Area')},
               {'src/b.ts': LABELS % ('KIND_LABELS', 'Areas')},
               'Label tables disagree', 'labels:src/a.ts:TYPE_LABELS'),
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
    assert code == 0 and len(_lines(text, 'impact: columns init-azure-sql.sql against backend/prisma/central/schema.prisma: ')) == 1, text
    line, = [line for line, _ in _last(tmp_path, 'impact: columns ') if 'central/schema.prisma' in line]
    assert line == ('impact: columns backend/prisma/central/init-azure-sql.sql against backend/prisma/central/schema.prisma: '
                    'backend/prisma/central/init-azure-sql.sql lacks central_employees (backend/prisma/central/init-azure-sql.sql:64) missing '
                    + ', '.join(('central_sync_attempted_at', 'central_sync_error', 'central_sync_state', 'external_type',
                                 'personnel_lifecycle_state', 'personnel_source', 'storage_scope'))
                    + '; missing table central_lending_assignments -> fix it, or say why in your report'), line
    # --all: the change added it, so it is the same impact line
    code, text = _static(tmp_path, '--all')
    assert code == 0 and [line for line, _ in _last(tmp_path, 'impact: columns ') if 'central/schema.prisma' in line] == [line], text


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
    # 4.3: the label drift is a 5.0-deprecated heuristic, a lead of show --last; the block, which the generated test
    # prints (or, inside a vitest run with FlowGuard's plugin, writes to static.json for the plugin's block), has the
    # declarations that differ.
    root = _planning(tmp_path / 'pt')
    frontend = root / 'frontend/src/utils/organization-navigation.ts'
    saved = frontend.read_bytes()
    frontend.unlink()
    _commit(root, {'package.json': '{"name": "pt", "private": true, "scripts": {"test": "vitest run"}, '
                                   '"devDependencies": {"vitest": "2.1.9"}}\n'})
    frontend.write_bytes(saved)
    code, text = _static(root)
    differ = _block(text)
    assert code == 0 and len(differ) == 1 and differ[0].startswith('impact: declarations OrganizationNavigationLabel: '), text
    shown = _cli_fixture.last(root).splitlines()
    assert shown[0].startswith('FlowGuard last run: check --static at ') and shown[1] == _cli_fixture.block(text)[0], shown
    drift = next(line for line in shown[shown.index('deprecated leads (5.0):'):] if 'My Organization' in line)
    assert "'My Organization'(backend/src/services/authority/organization-navigation.ts:" in drift, drift
    assert "'My organization'(frontend/src/utils/organization-navigation.ts:" in drift and 'spelling added in this task' in drift, drift
    code, text = _flowguard(root, 'init')
    assert code == 0 and 'Generated flowguard.static.test.mjs (vitest)' in text, text
    generated = root / 'flowguard.static.test.mjs'
    assert "import { test } from 'vitest';" in generated.read_text(encoding='utf-8')
    run = _run_generated(root, generated)
    output = _text(run.stdout + run.stderr)
    assert run.returncode == 0 and 'PASS FlowGuard check --static' in output, output
    assert differ[0] in output.splitlines(), output            # the same block, printed by the npm test
    _write(root, {'backend/src/services/notice.service.ts': '''
        export async function notice(prisma: any) {
          await prisma.auditEvent.create({ data: { severity: 'WARN' } });
        }
    '''})
    _planning(root, 'planning_tool_static')
    run = _run_generated(root, generated)
    output = _text(run.stdout + run.stderr)
    red = "red: values AuditEvent.severity: notice.service.ts:notice writes 'WARN' outside 'INFO'|'WARNING'|'ERROR'|'CRITICAL' -> use a declared value"
    # the planning_tool_static files are new in this change as well: their own 'WARN' is red too
    assert run.returncode == 1 and 'FAIL FlowGuard check --static: FlowGuard: 2 red, see the FlowGuard block at the end' in output, output
    assert red in output.splitlines(), output
    # Inside a vitest run with FlowGuard's plugin the lines go to <obs>/static.json, for the plugin's block at the end;
    # the test prints nothing and fails with the same one line.
    observations = tmp_path / 'obs'
    run = _run_generated(root, generated, env=dict(FLOWGUARD_VITEST_OBS=str(observations)))
    # stdout holds the stub runner's one line; check's deprecation notice reaches stderr (console.error)
    assert run.returncode == 1 and (run.stdout.splitlines(), run.stderr.splitlines()) == (
        ['FAIL FlowGuard check --static: FlowGuard: 2 red, see the FlowGuard block at the end'],
        ['deprecated: label-spelling leads goes in 5.0 -> do not use it']), run
    # one shape: what show --last keeps of the run (`signals.last_run`), with the parts of its first line
    from flowguard.intent import signals
    from flowguard.intent.vitest import static_lines
    saved = json.loads((observations / 'static.json').read_text(encoding='utf-8'))
    assert sorted(saved) == ['baseline', 'baseline_kind', 'compared', 'deprecated', 'hidden', 'ignored', 'lines', 'run', 'seconds',
                             'stamp', 'title', 'title_parts'], saved
    assert [line['text'] for line in saved['lines'] if line['kind'] == 'red'] == [
        "values AuditEvent.severity: backend/src/services/authority/authority-integrity-repair.service.ts:repairOrganizationAuthority writes "
        "'WARN' outside 'INFO'|'WARNING'|'ERROR'|'CRITICAL'",
        "values AuditEvent.severity: backend/src/services/notice.service.ts:notice writes 'WARN' outside 'INFO'|'WARNING'|'ERROR'|'CRITICAL'"]
    head = _git(root, 'rev-parse', 'HEAD').strip()
    assert saved['title_parts'] == dict(baseline=head, kind='task', ahead=0, option='--base'), saved
    assert (saved['run'], saved['baseline'], saved['baseline_kind'], saved['deprecated']) == (
        'check --static', head, 'task', ['label-spelling leads']), saved
    assert saved['title'] == signals.title(static_lines(observations)['lines'], **saved['title_parts'], seconds=saved['seconds']), saved
    assert saved['seconds'] > 0 and saved['ignored'] == 0 and any(lead['feature'] == 'label-spelling leads' for lead in saved['hidden'])
    # the vitest report reads it as it is (`vitest.static_lines`), and show --last names the run
    assert [line.kind for line in static_lines(observations)['lines']].count('red') == 2
    shown = _cli_fixture.last(root).splitlines()
    assert shown[0].startswith('FlowGuard last run: check --static at ') and shown[1] == saved['title'], shown
    run = _run_generated(root, generated, env=dict(FLOWGUARD_PYTHON=str(tmp_path / 'no-such-python')))
    output = _text(run.stdout + run.stderr)
    assert run.returncode == 1 and 'no Python that can import flowguard was found' in output, output
    assert 'set FLOWGUARD_PYTHON' in output and 'no-such-python' in output, output


def test_check_and_check_static_name_a_file_by_an_end_no_other_file_of_the_repository_has(tmp_path):
    # As in pytest's block (D17): pkg/policy.py never prints as policy.py in a repository that also has a policy.py,
    # though no line of the block names that other file.
    _commit(tmp_path, {'policy.py': 'def late_fee(days: int) -> int:\n    return days\n', 'pkg/__init__.py': '',
                       'pkg/policy.py': 'def late_fee(days: int) -> int:\n    return days * 2\n'})
    _write(tmp_path, {'pkg/policy.py': '# flowguard: same\ndef late_fee(days: int) -> int:\n    return days * 2\n'})
    for command in (('check', '--static'), ('check',)):
        code, text = _flowguard(tmp_path, *command)
        assert code == 1 and _block(text) == [
            'red: comment pkg/policy.py:1: invalid sensor anchor syntax -> correct this flowguard comment'], (command, text)


def test_check_static_says_known_fixed_for_a_ledger_finding_once_a_ledger_judges_every_handler(tmp_path):
    # As a pytest session: a ledger compared with the map in full judges every handler, so a known entry naming a ledger
    # finding that is no longer found may be fixed (`ran`); without a ledger nothing judged it.
    _commit(tmp_path, {'app.py': 'def load(path):\n    return open(path).read()\n', '.flowguard/known.toml': (
        '[known.old-handler]\nsites = ["app.py:load"]\nwhy = "load swallowed a missing file"\nact = "leave"\n'
        'finding = "ledger:app.py:2 load returns a default"\n')})
    code, text = _static(tmp_path)
    assert code == 0 and _block(text) == [], text
    assert _flowguard(tmp_path, 'ledger', 'init')[0] == 0
    fixed = ('known fixed?: known.old-handler: ledger:app.py:2 load returns a default no longer found '
             '-> the owner deferred it: revert, or say why in your report')
    for command in (('check', '--static'), ('check',)):     # check compares the ledger itself where no intent item runs
        code, text = _flowguard(tmp_path, *command)
        assert code == 0 and _block(text) == [fixed], (command, text)


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
    assert code == 0 and not _lines(text, 'lead: label spellings differ'), text
    code, text = _static(tmp_path, '--all')
    assert 'flowguard.static.test.mjs' not in text and 'flowguard.vitest.mjs' not in text, text


def test_check_static_all_lists_label_spellings_the_baseline_already_had(tmp_path):
    root = _planning(tmp_path / 'pt')
    _commit(root, {})                          # both spellings are old: nothing new to report
    code, text = _static(root)
    assert code == 0 and _block(text) == [] and not [lead for lead in _leads(root) if 'label spellings differ' in lead], text
    # --all keeps the old spellings for show --last (a 5.0-deprecated heuristic: a lead, no line of the block)
    code, text = _static(root, '--all')
    old = next(lead for lead in _leads(root) if 'label spellings differ' in lead and 'My Organization' in lead)
    assert old.startswith('label-spelling leads: before: label spellings differ: '), old
    assert "'My organization'(frontend/src/utils/organization-navigation.ts:" in old and 'spelling added in this task' not in old, old


def test_check_static_all_puts_the_new_lead_first_and_names_the_command_that_lists_every_lead(tmp_path):
    words = ['Alpha', 'Bravo', 'Charlie', 'Delta', 'Echo', 'Foxtrot', 'Golf', 'Hotel', 'India', 'Juliet', 'Kilo', 'Lima']
    _commit(tmp_path, {
        'src/upper.ts': ''.join(f"export function is{word}(x: string) {{ return x === '{word} Label'; }}\n" for word in words),
        'src/lower.ts': ''.join(f"export function was{word}(x: string) {{ return x === '{word.lower()} label'; }}\n" for word in words),
        'src/gamma.ts': "export function isGamma(x: string) { return x === 'Gamma Ray'; }\n",
    })
    # a label spelled another way ('Gamma ray'), not a key ('gamma-ray' is of another kind: literal_shape)
    _write(tmp_path, {'src/ray.ts': "export function isRay(x: string) { return x === 'Gamma ray'; }\n"})
    # 4.3: label spellings are a 5.0-deprecated heuristic, leads of show --last, which lists every one of them; --leads
    # is deprecated and lists the same.
    code, text = _static(tmp_path, '--all')
    leads = _leads(tmp_path)
    new = ["label-spelling leads: label spellings differ: 'Gamma Ray'(src/gamma.ts:1) and 'Gamma ray'(src/ray.ts:1, spelling added in this "
           'task) -> use one spelling, or read both from one reference']
    assert code == 0 and _block(text, everything=True) == [] and len(leads) == 13, text
    assert [lead for lead in leads if 'spelling added in this task' in lead] == new, leads
    assert all(lead.startswith('label-spelling leads: before: label spellings differ: ') for lead in leads if lead not in new), leads
    code, text = _static(tmp_path, '--all', '--leads')
    assert code == 0 and _leads(tmp_path) == leads, text
    assert 'deprecated: check --leads goes in 5.0 -> write python -m flowguard show --last' in text.splitlines(), text
    code, text = _static(tmp_path)
    assert code == 0 and _block(text) == [] and _leads(tmp_path) == new, text


def test_the_overflow_of_a_run_against_base_names_that_base_in_the_command_that_lists_every_lead(tmp_path):
    words = ['Alpha', 'Bravo', 'Charlie', 'Delta', 'Echo', 'Foxtrot', 'Golf', 'Hotel', 'India', 'Juliet', 'Kilo', 'Lima']
    _commit(tmp_path, {'src/upper.ts': ''.join(f"export function is{word}(x: string) {{ return x === '{word} Label'; }}\n"
                                               for word in words)})
    _write(tmp_path, {'src/lower.ts': ''.join(f"export function was{word}(x: string) {{ return x === '{word.lower()} label'; }}\n"
                                              for word in words)})
    _commit(tmp_path, message='twelve new spellings')
    # Against HEAD nothing is new; against HEAD~1 the twelve spellings are: the listing command keeps that base.
    code, text = _static(tmp_path, '--base', 'HEAD~1')
    assert code == 0 and re.fullmatch(r'FlowGuard \d+\.\d+ \(since --base HEAD~1\): 0 red; \d+\.\d s', text.splitlines()[0]), text
    leads = _leads(tmp_path)                # show --last lists every lead, against that base
    assert len(leads) == 12 and all(lead.endswith(', spelling added in this task) -> use one spelling, or read both from one reference')
                                    for lead in leads), leads
    code, text = _static(tmp_path, '--base', 'HEAD~1', '--leads')
    assert code == 0 and _leads(tmp_path) == leads, text
    code, text = _static(tmp_path)
    assert code == 0 and _leads(tmp_path) == [], text


def test_a_pytest_session_against_flowguard_base_names_that_base_and_keeps_its_leads_for_show_last(tmp_path):
    words = ['Alpha', 'Bravo', 'Charlie', 'Delta', 'Echo', 'Foxtrot', 'Golf', 'Hotel', 'India', 'Juliet', 'Kilo', 'Lima']
    _commit(tmp_path, {'src/upper.ts': ''.join(f"export function is{word}(x: string) {{ return x === '{word} Label'; }}\n"
                                               for word in words),
                       'pyproject.toml': '[tool.pytest.ini_options]\npythonpath = ["."]\ntestpaths = ["tests"]\n',
                       'tests/test_ok.py': 'def test_ok():\n    pass\n'})
    _write(tmp_path, {'src/lower.ts': ''.join(f"export function was{word}(x: string) {{ return x === '{word.lower()} label'; }}\n"
                                              for word in words)})
    _commit(tmp_path, message='twelve new spellings')
    # The session compares with HEAD~1 and says so; its label-spelling leads (5.0-deprecated) get no line of the
    # block: show --last lists all twelve, against that base.
    code, text = _pytest(tmp_path, '--flowguard-base', 'HEAD~1')
    base = _git(tmp_path, 'rev-parse', 'HEAD~1').strip()
    title, *lines = _cli_fixture.block(text)
    assert code == 0 and title.startswith(f'FlowGuard 4.2 (since --flowguard-base {base[:7]}): 0 red; ') and lines == [], text
    shown = _cli_fixture.last(tmp_path).splitlines()
    leads = shown[shown.index('deprecated leads (5.0):') + 1:]
    assert len(leads) == 12 and all(line.startswith('    label-spelling leads: label spellings differ: ') for line in leads), shown


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
    assert code == 0 and 'Open structure issue' not in text, text
    code, text = _static(tmp_path)
    assert code == 0 and _block(text) == [], text
    hold = tmp_path / 'shop/hold.py'
    hold.write_text(hold.read_text().replace("'held'", "'paused'"))
    # pytest and check --static print the 4.3 block: fields several files write without an agreement get no line of
    # their own (the impact line of a function whose written fields change names them); --all lists each writer.
    code, text = _pytest(tmp_path)
    assert code == 0 and _cli_fixture.block(text)[1:] == [], text
    code, text = _static(tmp_path)
    assert code == 0 and _block(text) == [], text
    code, text = _static(tmp_path, '--all')
    assert code == 0 and _block(text, everything=True) == [
        f'before: no writers agreement for Job.status at {name}.py:{name} was broken at task start -> leave it unless your task is about it'
        for name in ('close', 'hold', 'reopen')], text


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
    def touched():
        from flowguard.intent import owners
        cfg = _config(tmp_path)
        with closing(build(tmp_path)) as graph:
            return sorted(owners.touched_functions(owners.Change(cfg, graph, owners.baseline(cfg))))
    # Fields several files write without an agreement get no line of their own (--all lists them): what this change
    # touches decides their impact and before lines, `owners.touched_functions`.
    hold = tmp_path / 'src/hold.ts'
    hold.write_text('// flowguard: sensor HOLD_JOBS\n' + hold.read_text(encoding='utf-8'), encoding='utf-8')
    code, text = _static(tmp_path)
    assert code == 0 and _block(text) == [] and touched() == [], text      # the callback only moved one line down
    hold.write_text(hold.read_text(encoding='utf-8').replace("'held'", "'paused'"), encoding='utf-8')
    code, text = _static(tmp_path)
    assert code == 0 and _block(text) == [] and touched() == ['typescript/src/hold.ts:holdJobs'], text      # an edit inside it does


def test_a_structure_decision_closes_its_problem_and_a_decided_owner_needs_its_anchor(tmp_path):
    _commit(tmp_path, WRITERS)
    (tmp_path / 'owner.txt').write_text('Job.status belongs to the close workflow; the other writers must call it.\n')
    code, text = _flowguard(tmp_path, 'req', 'add', str(tmp_path / 'owner.txt'), '--id', 'R1')
    assert code == 0, text
    ledger = tmp_path / '.flowguard/ledger.toml'
    ledger.write_text('[structure."writers:Job.status"]\ndecision = "too short"\nsource = "R1"\n', encoding='utf-8')
    code, text = _static(tmp_path, '--all')
    assert code == 1 and 'Structure decision [structure."writers:Job.status"]: decision needs at least 8 words' in text, text
    ledger.write_text('[structure."writers:Job.status"]\ndecision = "close owns the status; hold and reopen will call close later"\n'
                      'source = "R9"\n', encoding='utf-8')
    code, text = _static(tmp_path, '--all')
    assert code == 1 and 'source "R9" is not stored owner wording' in text, text
    ledger.write_text('[structure."writers:Job.status"]\ndecision = "close owns the status; hold and reopen will call close later"\n'
                      'source = "R1"\n', encoding='utf-8')
    code, text = _static(tmp_path, '--all')
    # decided: the writers of Job.status are no longer listed
    assert code == 1 and _block(text, everything=True) == [
        'red: ledger [structure."writers:Job.status"]: ledger.toml:[structure."writers:Job.status"] records who writes the field, but no '
        'writers agreement exists -> add beside the responsible function: # flowguard: writers Job.status '
        'shop/close.py:close,shop/hold.py:hold,shop/reopen.py:reopen'], text
    close = tmp_path / 'shop/close.py'
    close.write_text('# flowguard: owner Job.status writers=close,hold,reopen\n' + close.read_text())
    code, text = _static(tmp_path, '--all')
    # the agreement holds now; what writes Job.status outside it was there at the baseline
    assert code == 0 and _block(text, everything=True) == [
        'before: writers Job.status at models.py:Job was broken at task start -> leave it unless your task is about it'], text


LATER = 'these fields require a newer FlowGuard; upgrade before reviewing them'
CLOSES = '. This entry closes no issue in the current version'


def test_a_structure_entry_with_fields_of_a_later_flowguard_is_unverified_and_closes_nothing(tmp_path):
    # Round 22 F5: FlowGuard 4.3 adds `status`, `sites`, `why`, `fix`, `ask` and `evidence` to [structure] entries.
    # 4.2 read a ledger written so as red ("未知字段 status"): a project on 4.3 and a clone still on 4.2 disagreed.
    _commit(tmp_path, WRITERS)
    ledger = tmp_path / '.flowguard/ledger.toml'
    ledger.parent.mkdir(exist_ok=True)
    ledger.write_text('[structure."writers:Job.status"]\nstatus = "known"\nsites = ["shop/hold.py:hold"]\n'
                      'why = "hold and reopen write the status beside close; the owner has not decided who owns it"\n'
                      'fix = "let hold and reopen call close"\n', encoding='utf-8')
    _commit(tmp_path, message='a 4.3 entry')
    grey = 'Structure entry [structure."writers:Job.status"] has fields this version does not recognize: fix, sites, status, why; ' + LATER
    writers = [f'before: no writers agreement for Job.status at {name}.py:{name} was broken at task start -> leave it unless your task is '
               'about it' for name in ('close', 'hold', 'reopen')]
    code, text = _static(tmp_path, '--all')
    # the entry closes no problem; the ledger is not compared, with the entry's reason (show --last in full)
    assert code == 0 and _block(text, everything=True) == writers + ['not compared: ledger.toml -> not a failure'], text
    assert unchecked(tmp_path) == {'.flowguard/ledger.toml': [grey + CLOSES]}, text
    code, text = _flowguard(tmp_path, 'ledger', 'check')
    assert code == 0 and 'not checked: ' + grey in text, text
    for run in (lambda: _static(tmp_path), lambda: _flowguard(tmp_path, 'check')):
        code, text = run()
        assert code == 0 and _block(text) == [
            'not compared: ledger.toml (Structure entry [structure."writers:Job.status"] has fields this version does...) -> not a failure'], text
        assert unchecked(tmp_path) == {'.flowguard/ledger.toml': [grey + CLOSES]}, text
    # pytest's block: one not compared line for the ledger, the entry's reason in show --last.
    code, text = _pytest(tmp_path)
    assert code == 0 and not re.search(r'^red: ', text, re.M), text
    assert ('not compared: ledger.toml (Structure entry [structure."writers:Job.status"] has fields this version does...) '
            '-> not a failure') in text.splitlines(), text
    assert any(grey in reason for reason in unchecked(tmp_path)['.flowguard/ledger.toml']), text
    # A decision with a field of a later FlowGuard beside it does not close its problem either.
    (tmp_path / 'owner.txt').write_text('Job.status belongs to the close workflow; the other writers must call it.\n')
    assert _flowguard(tmp_path, 'req', 'add', str(tmp_path / 'owner.txt'), '--id', 'R1')[0] == 0
    ledger.write_text('[structure."writers:Job.status"]\ndecision = "close owns the status; hold and reopen will call close later"\n'
                      'source = "R1"\nevidence = "the owner said so in the review"\n', encoding='utf-8')
    code, text = _static(tmp_path, '--all')
    assert code == 0 and unchecked(tmp_path) == {'.flowguard/ledger.toml': [
        'Structure entry [structure."writers:Job.status"] has fields this version does not recognize: evidence; ' + LATER + CLOSES]}, text
    assert _block(text, everything=True)[:3] == writers and not _lines(text, 'red: '), text


def test_a_later_field_leaves_the_known_fields_checked_and_a_misspelt_field_stays_red(tmp_path):
    # Round 22 F5 review: an entry with any field this version does not know was set aside unread, so a misspelt
    # `decison` was no longer red (exit 0) and the unstored source beside it was not shown at all.
    _commit(tmp_path, WRITERS)
    ledger = tmp_path / '.flowguard/ledger.toml'
    ledger.parent.mkdir(exist_ok=True)
    entry = '[structure."writers:Job.status"]\n'
    decision = 'decision = "close owns the status; hold and reopen will call close later"\n'
    ledger.write_text(entry + decision.replace('decision', 'decison', 1) + 'source = "R1"\n', encoding='utf-8')
    _commit(tmp_path, message='a misspelt entry')
    code, text = _flowguard(tmp_path, 'ledger', 'check')
    assert code == 1 and ('red: Structure decision [structure."writers:Job.status"]: unknown field decison (did you mean decision?)；missing decision；source "R1" is not stored owner wording') in text, text
    ledger.write_text(entry + decision + 'sorce = "R1"\n', encoding='utf-8')
    code, text = _flowguard(tmp_path, 'ledger', 'check')
    assert code == 1 and ': unknown field sorce (did you mean source?)；missing source' in text, text
    # A field of a later FlowGuard beside an unstored source: unverified, the source's error on the same line.
    ledger.write_text(entry + decision + 'source = "R1"\nevidence = "the owner said so in the review"\n', encoding='utf-8')
    code, text = _flowguard(tmp_path, 'ledger', 'check')
    line = next(line for line in text.splitlines() if 'evidence' in line)
    assert code == 0 and 'red: ' not in text and line.startswith('not checked: Structure entry [structure."writers:Job.status"] has fields this version does not recognize: evidence; ' + LATER), text
    assert 'source "R1" is not stored owner wording' in line, line
    # Second review: a field near decision or source beside that very field is no misspelling of it but another
    # field (`sources` beside `source`, `revision` beside `decision`): unverified, not red.
    for extra in ('sources = ["R1"]\n', 'revision = 2\n'):
        ledger.write_text(entry + decision + 'source = "R1"\n' + extra, encoding='utf-8')
        code, text = _flowguard(tmp_path, 'ledger', 'check')
        name = extra.partition(' ')[0]
        line = next((line for line in text.splitlines() if 'does not recognize: ' + name in line), None)
        assert code == 0 and 'red: ' not in text and line and line.startswith('not checked: '), text
    # Without the field it is near, it is that field misspelt, as before.
    ledger.write_text(entry + decision + 'sources = "R1"\n', encoding='utf-8')
    code, text = _flowguard(tmp_path, 'ledger', 'check')
    assert code == 1 and ': unknown field sources (did you mean source?)；missing source' in text, text


def test_the_session_brief_names_the_heaviest_open_structure_problems_in_one_line(tmp_path):
    _commit(tmp_path, WRITERS)
    code, before = _flowguard(tmp_path)
    assert code == 0, before
    code, text = _static(tmp_path, '--all')
    assert code == 0, text
    code, after = _flowguard(tmp_path)
    assert code == 0 and len(after.splitlines()) - len(before.splitlines()) == 1, (before, after)
    assert after.splitlines()[-1] == ('0 open structure issues (1 other fields have multiple writers and no writer agreement); highest severity: write Job.status (last check; check --static --all lists every issue and next step)'), after


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
    # 5.0-deprecated heuristics: leads of show --last, no line of the block
    assert code == 0 and _block(text) == [], text
    assert 'deprecated: old-value leads goes in 5.0 -> do not use it' in text.splitlines(), text
    leads = _leads(tmp_path)
    assert 'old-value leads: old values 14 remain in 1 decisions: src/reminders.ts:2 -> if requirements changed, update them together' in leads, leads
    alone = next(lead for lead in leads if lead.startswith('similar-implementation leads: lateFee'))
    assert alone.startswith('similar-implementation leads: lateFee(src/fees.ts:1) changed; previously identical copies: 1 unchanged: '
                            'src/legacy/fees.ts:1'), alone
    assert '// flowguard: same LATEFEE ref' in alone, alone


# ---- the ledger's TS catch fallbacks and a TS data owner, without pytest -----------------------------

def test_check_static_reports_a_new_typescript_fallback_and_a_write_outside_its_owner(tmp_path):
    _planning(tmp_path)
    _commit(tmp_path, {'backend/src/owners.ts': '// flowguard: owner Employee.organizationalUnitId writers=transferEmployee\nexport {};\n'})
    code, text = _flowguard(tmp_path, 'ledger', 'init')
    assert code == 0, text
    _commit(tmp_path, message='ledger')
    code, text = _static(tmp_path)
    assert code == 0 and _block(text) == [] and text.splitlines()[1:] == [
        'deprecated: owner writers= goes in 5.0 -> write writers FIELD FUNCTIONS'], text
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
    # the handler that hands its error to next() is no fallback; the entry to copy is the red's detail
    assert code == 1 and _lines(text, 'red: ') == [
        'red: ledger: New unregistered fallback: rogue.ts:9 catch any can end without raising -> python -m flowguard ledger check prints what to change',
        'red: writers Employee.organizationalUnitId: rogue.ts:moveEmployee writes Employee.organizationalUnitId outside transferEmployee '
        '-> call transferEmployee instead'], text
    assert '["backend/src/services/rogue.ts:moveEmployee:any"]' in _detail(tmp_path, 'red: ledger: New unregistered fallback: ')
    assert 'rogue.ts:4' not in _cli_fixture.last(tmp_path), text
