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
    # deleted (UserRole), counted inside OR (AuthorityAssignment), nulled (AuditEvent), Cascade (EmployeeLog), a
    # table no code creates or updates rows in (EmployeeBadge) and an optional self relation (Employee.supervisor)
    # are not listed.
    assert listed == 'EmployeeNote、EmployeeTransfer（3 个外键：decidedById、employeeId、requestedById）、Notification', listed
    assert '[structure."delete:backend/src/services/hard-delete.service.ts:removeEmployeeRow:Employee"]' in text, text


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


def test_the_files_init_writes_bring_no_label_spellings_of_their_own(tmp_path):
    _commit(tmp_path, {
        'package.json': '{"name": "app", "type": "module", "scripts": {"test": "vitest run"}, "devDependencies": {"vitest": "4.1.11"}}\n',
        'src/flags.ts': "export function known(x: string): boolean {\n  return x === '3' || x === 'c' || x === 'ROOT';\n}\n",
    })
    code, text = _flowguard(tmp_path, 'init')
    assert code == 0 and 'Generated flowguard.static.test.mjs (vitest)' in text, text
    code, text = _static(tmp_path)          # init's '-3', '-c' and '--root' are FlowGuard's, not the project's labels
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
    _write(tmp_path, {'src/ray.ts': "export function isRay(x: string) { return x === 'gamma-ray'; }\n"})
    code, text = _static(tmp_path, '--all')
    leads = _lines(text, '线索：')
    assert code == 0 and leads[0].startswith("线索：标签写法不一致：'Gamma Ray'"), text       # the new one first
    assert "'gamma-ray'（src/ray.ts:1，这次新增的写法）" in leads[0], leads
    assert leads[-1].startswith('线索：另 ') and leads[-1].endswith('条：python -m flowguard check --static --all --leads 列出全部线索'), leads
    code, text = _static(tmp_path, '--all', '--leads')
    every = _lines(text, '线索：')
    assert code == 0 and len(every) == 13 and every[0] == leads[0] and not any(line.startswith('线索：另 ') for line in every), text
    assert all(line.startswith('线索：旧账 标签写法不一致') for line in every[1:]), every
    code, text = _static(tmp_path)
    assert code == 0 and _lines(text, '线索：') == [leads[0]], text


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
