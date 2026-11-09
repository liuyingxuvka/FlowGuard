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


def test_check_static_all_lists_label_spellings_the_baseline_already_had(tmp_path):
    root = _planning(tmp_path / 'pt')
    _commit(root, {})                          # both spellings are old: nothing new to report
    code, text = _static(root)
    assert code == 0 and not _lines(text, '线索：标签写法不一致'), text
    code, text = _static(root, '--all')
    old = next(line for line in _lines(text, '线索：旧账 标签写法不一致') if 'My Organization' in line)
    assert "'My organization'（frontend/src/utils/organization-navigation.ts:" in old and '这次新增的写法' not in old, old


def test_init_writes_a_jest_test_for_a_jest_project_and_keeps_a_foreign_file(tmp_path):
    _commit(tmp_path, {'web/package.json': '{"name": "web", "scripts": {"test": "jest"}, "devDependencies": {"jest": "29.7.0"}}\n'})
    code, text = _flowguard(tmp_path, 'init')
    generated = tmp_path / 'web/flowguard.static.test.js'
    assert code == 0 and 'Generated web/flowguard.static.test.js (jest)' in text, text
    body = generated.read_text(encoding='utf-8')
    assert "require('node:child_process')" in body and 'path.resolve(__dirname, "..")' in body and 'vitest' not in body, body
    assert 'FLOWGUARD_PYTHON' in body and json.dumps(sys.executable) in body, body
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


def _pytest(root):
    bootstrap = ('import sys; sys.path.insert(0,sys.argv.pop(1)); import pytest; '
                 'raise SystemExit(pytest.main(sys.argv[1:]))')
    result = subprocess.run([sys.executable, '-c', bootstrap, SOURCE, '-q', '-p', 'flowguard.intent.plugin'], cwd=root,
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
