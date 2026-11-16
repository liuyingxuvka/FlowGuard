"""The impact line (design 4.6, stage 3 lane C): one `impact` line per function this change edits or adds whose
set of written fields changed, with counts and one name; `show Model.field` lists what the line counts.

Each fixture commits its baseline and edits the working tree; the lines are `owners.field_impact`'s, passed
through `signals.deliver` as lines already of their kind.
"""
from contextlib import closing

from flowguard.intent import anchors, owners, signals
from flowguard.intent.config import load_config
from flowguard.structure import build
from tests.intent_engine.test_static_check import _commit, _flowguard, _write

SCHEMA = '''
model Entry {
  id        String   @id
  value     Float
  note      String
  updatedAt DateTime
}
'''


def _update(function, data, comment=''):
    return comment + f"""export async function {function}(prisma: any) {{
  await prisma.entry.update({{ where: {{ id: '1' }}, data: {{ {data} }} }});
}}
"""


BASE = {
    'prisma/schema.prisma': SCHEMA,
    'app/set.ts': _update('setValue', "note: 'n'") + _update('keep', "note: 'k'"),
    'app/b.ts': _update('otherB', 'value: 1'),
    'app/c.ts': _update('otherC', 'value: 2'),
    'prisma/seed.ts': _update('seedEntries', 'value: 3'),
    'app/drop.ts': _update('dropNote', "note: 'd'"),
    'app/read.ts': '''export async function listEntries(prisma: any) { return prisma.entry.findMany({ where: { note: 'a' } }); }
export async function countEntries(prisma: any) { return prisma.entry.count({ where: { value: 1 } }); }
''',
    'tests/entry.test.ts': "export async function fixture(prisma: any) { return prisma.entry.findMany({ where: { id: '1' } }); }\n",
}
CHANGED = {
    # setValue now writes value (updatedAt is bookkeeping) and no longer note; keep writes what it wrote.
    'app/set.ts': _update('setValue', 'value: 4, updatedAt: new Date()') + _update('keep', "note: 'kept'"),
    'app/drop.ts': 'export async function dropNote(prisma: any) {\n  return prisma;\n}\n',
    'app/new.ts': _update('createEntry', "note: 'c'"),
    'prisma/seed.ts': _update('seedEntries', "value: 3, note: 's'"),          # a seed script: not reported
    'tests/entry.test.ts': "export async function fixture(prisma: any) {\n  return prisma.entry.update({ where: { id: '1' }, data: { note: 't' } });\n}\n",
}


def _impact(root, base='HEAD'):
    cfg = load_config(root)
    with closing(build(root, roots=cfg.roots)) as graph:
        index = anchors.collect(graph)
        found = owners.field_impact(owners.Change(cfg, graph, base), index)
        modules = dict(graph.con.execute('SELECT path, module FROM file'))
    return found, modules


def test_a_changed_function_whose_written_fields_changed_gets_one_impact_line_with_counts_and_one_name(tmp_path):
    _commit(tmp_path, BASE)
    _write(tmp_path, CHANGED)
    found, modules = _impact(tmp_path)
    lines, _ = signals.deliver([], touched_functions=(), touched_files=(), extra=found.lines)
    by_function = {line.function: line for line in lines}
    assert [line.kind for line in lines] == ['impact'] * 3 and not found.issues
    assert sorted(by_function) == sorted([modules['app/set.ts'] + ':setValue', modules['app/drop.ts'] + ':dropNote',
                                          modules['app/new.ts'] + ':createEntry'])
    line = by_function[modules['app/set.ts'] + ':setValue']
    # Other writers of Entry.value: otherB and otherC (the seed script is left out); four files write it without a
    # writers agreement (the seed's too); two functions read Entry (the test file's fixture now updates it).
    assert line.name == 'impact:' + line.function and line.places == ('app/set.ts:setValue',)
    assert line.text == ('setValue now writes Entry.value; no longer writes Entry.note; 2 other writers (no writers agreement), '
                         '2 readers of Entry')
    assert line.step == 'check them for this change only (python -m flowguard show Entry.value)'
    assert sorted(line.detail) == sorted([f'other writer of Entry.value: {modules["app/b.ts"]}:otherB',
                                          f'other writer of Entry.value: {modules["app/c.ts"]}:otherC',
                                          f'reader of Entry: {modules["app/read.ts"]}:countEntries',
                                          f'reader of Entry: {modules["app/read.ts"]}:listEntries'])
    # An added function; one that only stopped writing a field. keep, createEntry and the seed write Entry.note now:
    # three files without a writers agreement, of which two production functions besides each.
    assert by_function[modules['app/new.ts'] + ':createEntry'].text == \
        'createEntry now writes Entry.note; 1 other writer (no writers agreement), 2 readers of Entry'
    assert by_function[modules['app/drop.ts'] + ':dropNote'].text == \
        'dropNote no longer writes Entry.note; 2 other writers (no writers agreement), 2 readers of Entry'
    assert by_function[modules['app/drop.ts'] + ':dropNote'].step.endswith('(python -m flowguard show Entry.note)')


def test_a_writers_agreement_on_the_field_leaves_out_the_merged_writers_problem_and_no_baseline_gives_no_line(tmp_path):
    agreement = '// flowguard: writers Entry.value setValue,app/b.ts:otherB,app/c.ts:otherC,prisma/seed.ts:seedEntries\n'
    _commit(tmp_path, {**BASE, 'app/set.ts': _update('setValue', "note: 'n'", agreement)})
    _write(tmp_path, {'app/set.ts': _update('setValue', 'value: 4', agreement)})
    found, modules = _impact(tmp_path)
    # Every function that reads the model counts, the test file's fixture too.
    assert [line.text for line in found.lines] == ['setValue now writes Entry.value; no longer writes Entry.note; 2 other writers, 3 readers of Entry']
    assert _impact(tmp_path, base=None)[0].lines == []


def test_the_static_assembly_carries_the_impact_lines(tmp_path):
    _commit(tmp_path, BASE)
    _write(tmp_path, {'app/new.ts': _update('createEntry', "note: 'c'")})
    cfg = load_config(tmp_path)
    with closing(build(tmp_path, roots=cfg.roots)) as graph:
        found = owners.static_findings(cfg, graph, anchors.collect(graph), 'HEAD')
    assert [(line.kind, line.name.partition(':')[0]) for line in found.lines] == [('impact', 'impact')]
    lines, _ = signals.deliver(found.issues, touched_functions=found.touched_functions, touched_files=found.touched_files,
                               ran=found.ran, extra=found.lines)
    # No code creates Entry rows: the new update is also a new member of that structure finding, an impact line too.
    assert sorted((line.kind, line.name) for line in lines) == [('impact', 'impact:typescript/app/new.ts:createEntry'),
                                                               ('impact', 'uncreated:Entry')]


def test_show_of_a_field_lists_its_models_readers_the_callers_of_its_writers_and_the_tests_that_reach_them(tmp_path):
    _commit(tmp_path, {
        **BASE,
        'app/__init__.py': '',
        'app/model.py': 'class Account:\n    status: str\n',
        'app/service.py': 'from app.model import Account\n\n\ndef close(account: Account):\n    account.status = "closed"\n',
        'app/api.py': 'from app.service import close\n\n\ndef handle(account):\n    return close(account)\n',
        'tests/test_service.py': 'from app.service import close\n\n\ndef test_close():\n    assert close is not None\n',
    })
    code, text = _flowguard(tmp_path, 'show', 'Account.status', '--full')
    lines = text.splitlines()
    assert code == 0, text
    assert 'writes Account.status app/service.py:5 close (assign)' in lines, text
    assert 'caller of close: handle (app/api.py:4)' in lines, text
    assert 'test tests/test_service.py reaches a writer of Account.status' in lines, text
    code, text = _flowguard(tmp_path, 'show', 'Entry.value', '--full')
    lines = text.splitlines()
    assert code == 0, text
    assert 'reads Entry app/read.ts:1 listEntries (findMany)' in lines and 'reads Entry app/read.ts:2 countEntries (count)' in lines, text
    assert 'reads Entry tests/entry.test.ts:1 fixture (findMany)' in lines, text       # every read of the model


def test_show_of_a_name_starts_with_what_the_map_read_about_it(tmp_path):
    # Planning Tool's docs said fte_share is 0..1 while the schemas declare it differently in places: show NAME first
    # says how each schema and SQL file declares a field, the value set read for it, a constant's value and an
    # enum's members, before who writes or reads it; a declaration that differs between files is a line of its own.
    _commit(tmp_path, {
        'prisma/schema.prisma': 'model Job {\n  id    String  @id\n  share Decimal @map("job_share")\n  state String\n  @@map("jobs")\n}\n',
        'prisma/schema.sqlite.prisma': 'model Job {\n  id    String  @id\n  share Decimal @map("job_share")\n  state Int\n  @@map("jobs")\n}\n',
        'db/setup.sql': "CREATE TABLE jobs (\n  id NVARCHAR(36) PRIMARY KEY,\n  job_share DECIMAL(6,4) NOT NULL CHECK (job_share >= 0 AND job_share <= 2),\n"
                        "  state NVARCHAR(20) CHECK (state IN ('NEW', 'DONE'))\n);\n"
                        "ALTER TABLE jobs ADD CONSTRAINT chk_share CHECK ([job_share] BETWEEN 0.0 AND 1.0);\n"
                        "/* ALTER TABLE jobs ADD CONSTRAINT chk_old CHECK (job_share < 5); */\n",
        'app/limits.ts': "const MAX_SHARE = 2;\nexport const JobKind = { A: 'A', B: 'B' } as const;\n"
                         "export function shareLimit(kind: string) { return kind === JobKind.A ? MAX_SHARE : 1; }\n",
        'app/schemas.ts': "const MAX_SHARE = 2;\nexport const createJob = z.object({ share: z.number().min(0).max(1), id: z.string() });\n"
                          "const shareSchema = z\n  .number()\n  .gt(0)\n  .lte(MAX_SHARE);\nexport const editJob = z.object({ share: shareSchema });\n",
    })
    code, text = _flowguard(tmp_path, 'show', 'Job.share')
    lines = text.splitlines()
    # Each CHECK range is a line of its own, as SQL spells its bounds; one in a comment is not SQL that runs.
    assert code == 0 and lines[2:6] == ['declared Job.share: Decimal @map("job_share") (prisma/schema.prisma:3, prisma/schema.sqlite.prisma:3)',
                                        'column jobs.job_share DECIMAL(6,4) (db/setup.sql:3)',
                                        'range jobs.job_share: 0 <= job_share <= 2 (CHECK db/setup.sql:3)',
                                        'range jobs.job_share: 0.0 <= job_share <= 1.0 (CHECK db/setup.sql:6)'], text
    # zod schemas of a key of that name, read from the source: inline, or a constant of the same file it names; each
    # line names the schema object the key belongs to and that the key matched by its name.
    assert lines[6:8] == ['zod key share in createJob: 0 <= share <= 1 (app/schemas.ts:2)',
                          'zod key share in editJob: 0 < share <= MAX_SHARE=2 (app/schemas.ts:7)'], text
    code, text = _flowguard(tmp_path, 'show', 'Job.state')
    lines = text.splitlines()
    assert code == 0 and lines[2:6] == ['declared Job.state: String (prisma/schema.prisma:4)', 'declared Job.state: Int (prisma/schema.sqlite.prisma:4)',
                                        'column jobs.state NVARCHAR(20) (db/setup.sql:4)', 'values Job.state: NEW | DONE (CHECK db/setup.sql:4)'], text
    code, text = _flowguard(tmp_path, 'show', 'MAX_SHARE')
    lines = text.splitlines()
    # The map knows the name itself, so functions that merely share a word with it wait for --full, which it says.
    assert code == 0 and lines[2:] == ['const MAX_SHARE = 2 (app/limits.ts:1, app/schemas.ts:1)',
                                       '... 1 more lines: python -m flowguard show MAX_SHARE --full lists them all'], text
    code, text = _flowguard(tmp_path, 'show', 'MAX_SHARE', '--full')
    assert code == 0 and 'shareLimit' in text and 'more lines' not in text, text
    code, text = _flowguard(tmp_path, 'show', 'JobKind')
    assert code == 0 and text.splitlines()[2:] == ['values JobKind: A | B (app/limits.ts:2)'], text


PT_SCHEMA = """datasource db {
  provider = "sqlserver"
  url      = env("DATABASE_URL")
}

model Assignment {
  id       String  @id
  fteShare Decimal @map("fte_share")
  status   String  @default("DRAFT")
  @@map("assignments")
}
"""
# Planning Tool's zod schemas, as backend/src/api/schemas/*.schemas.ts spell them (2026-11): a shared constant, a refined
# or optional constant, nested arrays of objects, `z\n.object(` inside a helper call, `.partial().extend(` of another
# schema and one schema object holding the key twice.
PT_ZOD = {
    'backend/src/api/schemas/allocation.schemas.ts': """import { z } from 'zod';

const identity = z.string().uuid();
const fte = z.number().finite().min(0).max(2);
const periodFields = { periodStart: z.string(), periodEnd: z.string() };

export const allocationPeriodSchema = z.object({
  ...periodFields, fteShare: fte,
}).strict().refine((value) => value.periodStart <= value.periodEnd, 'Period start must not follow its end.');

export const allocationCreateSchema = z.object({
  employeeId: identity, ...periodFields,
  fteShare: fte.refine((value) => value > 0, 'A new allocation must be greater than zero.'),
}).strict();
""",
    'backend/src/api/schemas/assignment.schemas.ts': """import { z } from 'zod';

export const batchAssignSchema = z.object({
  assignments: z
    .array(
      z.object({
        employeeId: z.string().trim().min(1, 'Employee ID is required'),
        periods: z
          .array(
            z.object({
              fteShare: z.number().min(0, 'FTE share must be >= 0').max(1, 'FTE share must be <= 1'),
            }).strict(),
          )
          .min(1, 'At least one period is required'),
      }).strict(),
    )
    .min(1),
}).strict();
""",
    'backend/src/api/schemas/personnel-mvp.schemas.ts': """import { z } from 'zod';

const MAX_FTE_SHARE = 2.0;
const dateRangeBaseSchema = z.object({ startDate: z.string(), endDate: z.string() });

export const lendingUpdateSchema = requireAtLeastOneValue(
  z
    .object({
      fteShare: z.number().gt(0).lte(1).optional(),
    })
    .refine(({ fteShare }) => fteShare !== 0),
  'At least one update field is required.',
);

export const capacityEntryCreateSchema = dateRangeBaseSchema
  .partial()
  .extend({
    fteShare: z.number().nonnegative().max(MAX_FTE_SHARE),
  });

const phases = z.union([
  z.object({ kind: z.literal('a'), fteShare: z.number().gt(0).lte(1) }),
  z.object({ kind: z.literal('b'), fteShare: z.number().gt(0).lte(1) }),
]);

function requireAtLeastOneValue<T>(schema: T, message: string): T { return schema; }
""",
    # an object key of that name that is no zod schema, a type member, a test file's schema: no zod line
    'frontend/src/utils/add-project-quantity.ts': """export interface QuantityRow { fteShare: number }
export const emptyRow = { fteShare: 0 };
export function roundFteShare(value: number): number { return Math.round(value * 100) / 100; }
""",
    'backend/tests/unit/allocation.schemas.test.ts': """import { z } from 'zod';
const fixture = z.object({ fteShare: z.number().max(9) });
""",
}


def test_show_names_the_zod_schema_object_each_key_belongs_to_and_says_the_key_matched_by_name(tmp_path):
    """Planning Tool (T4): `show Assignment.fteShare` printed `zod 0 <= fteShare <= 2 (allocation.schemas.ts:25, ...)`
    for every TS object key named fteShare, and `show ProjectAssignment.fteShare`, a model that does not exist, the
    same lines. Each zod line now names the schema object the key belongs to, as the source spells it (the nearest
    enclosing `const NAME = z.object(`, `NAME: z.object(` or `.extend(` whose result the source names, else the
    declaration holding it), identical bounds of one schema object on one line; a test file's schema is left out. A
    model the map does not know gets no zod line, and a line says why."""
    _commit(tmp_path, {'backend/prisma/schema.prisma': PT_SCHEMA, **PT_ZOD})
    code, text = _flowguard(tmp_path, 'show', 'Assignment.fteShare')
    assert code == 0, text
    allocation, assignment, personnel = (f'backend/src/api/schemas/{name}.schemas.ts' for name in ('allocation', 'assignment', 'personnel-mvp'))
    assert [line for line in text.splitlines() if line.startswith('zod')] == [
        f'zod key fteShare in allocationPeriodSchema: 0 <= fteShare <= 2 ({allocation}:8)',
        f'zod key fteShare in allocationCreateSchema: 0 <= fteShare <= 2 ({allocation}:13)',
        f'zod key fteShare in batchAssignSchema: 0 <= fteShare <= 1 ({assignment}:11)',
        f'zod key fteShare in lendingUpdateSchema: 0 < fteShare <= 1 ({personnel}:9)',
        f'zod key fteShare in capacityEntryCreateSchema: 0 <= fteShare <= MAX_FTE_SHARE=2.0 ({personnel}:18)',
        f'zod key fteShare in phases: 0 < fteShare <= 1 ({personnel}:22, {personnel}:23)'], text
    code, text = _flowguard(tmp_path, 'show', 'ProjectAssignment.fteShare')
    lines = text.splitlines()
    assert code == 0 and not [line for line in lines if line.startswith('zod')], text
    assert lines[2] == ('not on the map: no Prisma model, database table, TS type or class ProjectAssignment; the zod keys '
                        'fteShare of 6 schema objects are not listed, as a key matches by its name alone; Prisma models '
                        'with a field fteShare: Assignment'), text
    # no line claims the map knows the name: the functions that share a word with it are listed, not held for --full
    assert any('roundFteShare' in line for line in lines) and 'more lines' not in text, text


def test_show_leaves_out_the_value_sets_and_constants_only_test_files_declare(tmp_path):
    """Planning Tool (T4): `show` took 228 value sets and 55 declarations from files under tests/ and e2e specs (an
    `interface AccessRow` of a test, a test's `as const` list). Its values and const lines now leave out what only
    test files declare (`is_test_file`, the map's test flag); production declarations are listed as before."""
    _commit(tmp_path, {
        'app/limits.ts': "export const MAX_ROWS = 10;\nexport type AccessKind = 'read' | 'write';\n",
        'app/row.ts': "export interface PlanRow { action: 'read' | 'write' }\n",
        'backend/tests/unit/access.test.ts': ("const MAX_ROWS = 50;\nexport const ROLES = ['admin', 'viewer'] as const;\n"
                                              "interface AccessRow { action: 'read_planning' | 'create' }\n"
                                              "export type AccessKind = 'read' | 'write' | 'delete';\n"),
        'e2e/flows.spec.ts': 'const MAX_ROWS = 70;\nconst STEPS = [1, 2];\n',
    })
    def shown(name):
        code, text = _flowguard(tmp_path, 'show', name)
        assert code == 0, text
        return [line for line in text.splitlines() if line.startswith(('const ', 'values '))]
    assert shown('MAX_ROWS') == ['const MAX_ROWS = 10 (app/limits.ts:1)']
    assert shown('AccessKind') == ['values AccessKind: read | write (app/limits.ts:2)']
    assert shown('PlanRow.action') == ['values PlanRow.action: read | write (app/row.ts:1)']
    assert shown('ROLES') == shown('STEPS') == shown('AccessRow.action') == []


def test_show_of_an_anchored_field_also_says_how_it_is_declared_and_who_writes_it(tmp_path):
    """Planning Tool (T4): `show CentralEmployee.orgUnitId` took the ANCHOR branch (a together agreement names it) and
    printed none of the declaration, column and writes lines `show Employee.organizationalUnitId` printed. The
    ANCHOR branch of a Model.field now prints them too, after the agreement; a write the agreement lines name
    (outside its writers, a test fixture) is not listed again."""
    _commit(tmp_path, {
        'backend/prisma/central/schema.prisma': """datasource db {
  provider = "sqlserver"
  url      = env("CENTRAL_DATABASE_URL")
}

model CentralEmployee {
  id        String  @id
  orgUnitId String? @map("org_unit_id")
  @@map("central_employees")
}
""",
        'backend/prisma/central/migrations/20260330131802_init_central_org/migration.sql':
            'CREATE TABLE "central_employees" (\n  "id" TEXT NOT NULL PRIMARY KEY,\n  "org_unit_id" TEXT\n);\n',
        'backend/prisma/schema.prisma': """datasource db {
  provider = "sqlserver"
  url      = env("DATABASE_URL")
}

model Employee {
  id                   String @id
  organizationalUnitId String @map("organizational_unit_id")
  @@map("employees")
}

model Project {
  id                String @id
  lifecycleStatusId String @map("lifecycle_status_id")
  @@map("projects")
}
""",
        'backend/src/services/employee-home-unit.service.ts': """// flowguard: together CentralEmployee.orgUnitId Employee.organizationalUnitId except=backend/prisma/migrate-to-central.ts:migrateEmployees(one-off script)
export async function changeEmployeeHomeUnit(prisma: any, central: any, id: string, unit: string) {
  await prisma.employee.updateMany({ where: { id }, data: { organizationalUnitId: unit } });
  await central.centralEmployee.updateMany({ where: { id }, data: { orgUnitId: unit } });
}
""",
        'backend/prisma/migrate-to-central.ts': """export async function migrateEmployees(central: any, id: string, unit: string) {
  await central.centralEmployee.create({ data: { id, orgUnitId: unit } });
}
""",
        'backend/src/services/project.service.ts': """// flowguard: writers Project.lifecycleStatusId projectService.create,projectService.update
export const projectService = {
  async create(prisma: any) { return prisma.project.create({ data: { id: 'p', lifecycleStatusId: 'L1' } }); },
  async update(prisma: any, id: string) { return prisma.project.update({ where: { id }, data: { lifecycleStatusId: 'L2' } }); },
};
export async function softDelete(prisma: any, id: string) {
  return prisma.project.update({ where: { id }, data: { lifecycleStatusId: 'DELETED' } });
}
""",
    })
    code, text = _flowguard(tmp_path, 'show', 'CentralEmployee.orgUnitId')
    lines = text.splitlines()
    assert code == 0 and lines[0] == 'ANCHOR CentralEmployee.orgUnitId' and lines[2].startswith('together CentralEmployee.orgUnitId'), text
    facts = lines[lines.index(next(line for line in lines if line.startswith('fix: '))) + 1:][:4]
    assert facts == [
        'declared CentralEmployee.orgUnitId: String? @map("org_unit_id") (backend/prisma/central/schema.prisma:8)',
        'column central_employees.org_unit_id TEXT (backend/prisma/central/migrations/20260330131802_init_central_org/migration.sql:3)',
        'writes CentralEmployee.orgUnitId backend/prisma/migrate-to-central.ts:2 migrateEmployees (create)',
        'writes CentralEmployee.orgUnitId backend/src/services/employee-home-unit.service.ts:4 changeEmployeeHomeUnit (updateMany)'], text
    code, text = _flowguard(tmp_path, 'show', 'Project.lifecycleStatusId')
    lines = text.splitlines()
    assert code == 0 and lines[0] == 'ANCHOR Project.lifecycleStatusId', text
    assert 'outside writers: backend/src/services/project.service.ts:7 softDelete (update)' in lines, text
    # the writers' own writes are listed; softDelete's, named above as outside the writers, is not listed again
    assert [line for line in lines if line.startswith(('declared ', 'writes '))] == [
        'declared Project.lifecycleStatusId: String @map("lifecycle_status_id") (backend/prisma/schema.prisma:14)',
        'writes Project.lifecycleStatusId backend/src/services/project.service.ts:3 create (create)',
        'writes Project.lifecycleStatusId backend/src/services/project.service.ts:4 update (update)'], text
    assert len(lines) == len(set(lines)), text


def test_show_lists_the_enum_a_prisma_schema_not_in_use_types_the_field_with(tmp_path):
    """Planning Tool (T4): `show Assignment.status` printed the String declarations and the CHECK set, not the enum
    AssignmentStatus that backend/prisma/schema.sqlite.prisma (a provider template, not in use) types the field with:
    the values lines came from `value_sets()`, the schemas in use only. show now lists, for each Prisma schema that
    types the field with an enum, its members and where it is declared, saying when that schema is not in use;
    `value_sets()`, which the values check reads, is as before."""
    sqlite = """datasource db {
  provider = "sqlite"
  url      = "file:./dev.db"
}

enum AssignmentStatus {
  DRAFT
  ACTIVE
  CLOSED
}

enum DemandStatus {
  OPEN
  DONE
}

model Assignment {
  id     String           @id
  status AssignmentStatus @default(DRAFT)
}

model Demand {
  id     String       @id
  status DemandStatus @default(OPEN)
}
"""
    in_use = PT_SCHEMA + '\nenum DemandStatus {\n  OPEN\n  DONE\n}\n\nmodel Demand {\n  id     String       @id\n  status DemandStatus @default(OPEN)\n}\n'
    _commit(tmp_path, {'backend/prisma/schema.prisma': in_use, 'backend/prisma/schema.sqlite.prisma': sqlite})
    code, text = _flowguard(tmp_path, 'show', 'Assignment.status')
    lines = text.splitlines()
    assert code == 0 and [line for line in lines if line.startswith(('declared ', 'values '))] == [
        'declared Assignment.status: String @default("DRAFT") (backend/prisma/schema.prisma:9)',
        'declared Assignment.status: AssignmentStatus @default(DRAFT) (backend/prisma/schema.sqlite.prisma:19)',
        'values Assignment.status: DRAFT | ACTIVE | CLOSED (enum AssignmentStatus backend/prisma/schema.sqlite.prisma:6, '
        'a schema not in use)'], text
    # The enum of the schema in use as value_sets gives it, once; the template's own enum beside it.
    code, text = _flowguard(tmp_path, 'show', 'Demand.status')
    assert code == 0 and [line for line in text.splitlines() if line.startswith('values ')] == [
        'values Demand.status: OPEN | DONE (enum DemandStatus (backend/prisma/schema.prisma:13))',
        'values Demand.status: OPEN | DONE (enum DemandStatus backend/prisma/schema.sqlite.prisma:12, a schema not in use)'], text
    cfg = load_config(tmp_path)
    with closing(build(tmp_path, roots=cfg.roots)) as graph:
        assert [(row['key'], row['files']) for row in graph.value_sets()] == [('Demand.status', ('backend/prisma/schema.prisma',))]


def test_show_prints_a_module_constant_that_is_an_array_of_literals(tmp_path):
    """Planning Tool (T4): `show PROBABILITY_STEPS` printed nothing, though two files declare `const PROBABILITY_STEPS =
    [0, 5, 50, 75, 90, 100] as const`: the JS/TS reader kept a module constant's right side as a literal only for one
    scalar, so neither the array nor its `as const` wrapper gave an assignment row. A module-level array of literals
    is now one; a string `as const` array stays a value set (its values line, not a second const line)."""
    _commit(tmp_path, {
        'frontend/src/components/projects/ProjectProbabilityEditor.tsx': """/**
 * @exports PROBABILITY_STEPS - Selectable planning probability values.
 */
export const PROBABILITY_STEPS = [0, 5, 50, 75, 90, 100] as const;

export function ProjectProbabilityEditor({ value }: { value: number }) {
  return <select value={value}>{PROBABILITY_STEPS.map((step) => <option key={step} value={step}>{step}%</option>)}</select>;
}
""",
        'frontend/src/pages/ProjectDetailPage.tsx': """const PROBABILITY_STEPS = [0, 5, 50, 75, 90, 100] as const;
const SCOPE_LEVELS = ['OWN', 'TEAM', 'ALL'] as const;
const MONTH_NAMES = ['Jan', 'Feb', 'Mar'];
const OFFSETS = [-2.5, 0, 4];
const MIXED = [1, ...OFFSETS];

export function ProjectDetailPage() {
  const LOCAL_STEPS = [1, 2];
  return <div>{PROBABILITY_STEPS.length + LOCAL_STEPS.length + SCOPE_LEVELS.length + MONTH_NAMES.length + MIXED.length}</div>;
}
""",
    })
    def shown(name):
        code, text = _flowguard(tmp_path, 'show', name)
        assert code == 0, text
        return [line for line in text.splitlines() if line.startswith(('const ', 'values '))]
    assert shown('PROBABILITY_STEPS') == ['const PROBABILITY_STEPS = [0, 5, 50, 75, 90, 100] '
                                          '(frontend/src/components/projects/ProjectProbabilityEditor.tsx:4, frontend/src/pages/ProjectDetailPage.tsx:1)']
    assert shown('SCOPE_LEVELS') == ['values SCOPE_LEVELS: OWN | TEAM | ALL (frontend/src/pages/ProjectDetailPage.tsx:2)']
    assert shown('MONTH_NAMES') == ['const MONTH_NAMES = ["Jan", "Feb", "Mar"] (frontend/src/pages/ProjectDetailPage.tsx:3)']
    assert shown('OFFSETS') == ['const OFFSETS = [-2.5, 0, 4] (frontend/src/pages/ProjectDetailPage.tsx:4)']
    assert shown('MIXED') == shown('LOCAL_STEPS') == []          # a spread is no literal; a function's own array is no module constant
    # The other readers of assignment rows are as before: a module constant is no write of a field, also by name.
    cfg = load_config(tmp_path)
    with closing(build(tmp_path, roots=cfg.roots)) as graph:
        assert [row for row in graph.writes(by_name=True) if row['file'].startswith('frontend/')] == []
    code, text = _flowguard(tmp_path, 'check', '--static')
    assert code == 0, text


def test_a_check_constraint_that_code_builds_as_a_string_is_not_read_as_a_range_or_a_value_set(tmp_path):
    """A stated limit, not a wish (T4, U2.6): Planning Tool adds `chk_project_source_type` with
    `prisma.$executeRawUnsafe(\\`ALTER TABLE ... CHECK ([source_type] IN (...))\\`)` in
    backend/prisma/migrate-add-import-source-type.ts. FlowGuard reads ranges and CHECK sets from `.sql` files only
    (docs/intent-guide.md says so where show's facts are described): SQL that code builds as a string and runs gives
    `show` no range and no values line, and the values check no set. This test pins the limit; it does not ask for a
    reader of such strings."""
    _commit(tmp_path, {
        'backend/prisma/schema.prisma': """datasource db {
  provider = "sqlserver"
  url      = env("DATABASE_URL")
}

model Project {
  id         String  @id
  sourceType String  @map("source_type")
  share      Decimal @map("share")
  @@map("projects")
}
""",
        'backend/prisma/migrate-add-import-source-type.ts': """import { prisma } from '../src/utils/prisma.js';

async function main(): Promise<void> {
  await prisma.$executeRawUnsafe(
    `ALTER TABLE [projects]
       ADD CONSTRAINT [chk_project_source_type]
       CHECK ([source_type] IN ('MANUAL', 'SAP_CATALOG', 'IMPORT'))`,
  );
  await prisma.$executeRawUnsafe(`ALTER TABLE [projects] ADD CONSTRAINT [chk_share] CHECK ([share] >= 0 AND [share] <= 1)`);
}

main();
""",
    })
    for name, declared in (('Project.sourceType', 'String @map("source_type")'), ('Project.share', 'Decimal @map("share")')):
        code, text = _flowguard(tmp_path, 'show', name)
        lines = text.splitlines()
        assert code == 0 and lines[2] == f'declared {name}: {declared} (backend/prisma/schema.prisma:{8 if "source" in name else 9})', text
        assert not [line for line in lines if line.startswith(('range ', 'values '))], text
    cfg = load_config(tmp_path)
    with closing(build(tmp_path, roots=cfg.roots)) as graph:
        assert graph.value_sets() == []


def test_a_function_that_stops_writing_one_of_two_fields_gets_its_line_and_the_static_check_still_runs(tmp_path):
    # It still writes Entry.value, so the field it no longer writes is found among the baseline's rows only.
    _commit(tmp_path, {'prisma/schema.prisma': SCHEMA, 'app/set.ts': _update('setBoth', "value: 1, note: 'n'")})
    _write(tmp_path, {'app/set.ts': _update('setBoth', 'value: 1')})
    found, modules = _impact(tmp_path)
    assert [(line.function, line.text, line.places) for line in found.lines] == [
        (modules['app/set.ts'] + ':setBoth', 'setBoth no longer writes Entry.note; 0 other writers, 0 readers of Entry',
         ('app/set.ts:setBoth',))]
    assert found.lines[0].step == 'check them for this change only (python -m flowguard show Entry.note)'
    cfg = load_config(tmp_path)
    with closing(build(tmp_path, roots=cfg.roots)) as graph:
        assembled = owners.static_findings(cfg, graph, anchors.collect(graph), 'HEAD')
    assert [line.text for line in assembled.lines if line.kind == 'impact'] == [found.lines[0].text]
    code, text = _flowguard(tmp_path, 'check', '--static')
    assert code == 0 and 'Traceback' not in text, text


def test_a_sql_write_is_shown_by_its_column_and_a_select_of_its_table_counts_as_a_reader(tmp_path):
    """SQL in string literals (Python): `show table.column` names the column each UPDATE writes, and the impact line
    and show count the function whose SELECT reads that table, in the number each count needs."""
    store = '''def reserve(db, booking_id, unit):
    db.execute("UPDATE booking SET unit_id = ? WHERE id = ?", (unit, booking_id))


def release(db, booking_id):
    db.execute("UPDATE booking SET unit_id = NULL WHERE id = ?", (booking_id,))


def close_day(db, booking_id):
    db.execute("UPDATE booking SET note = 'closed' WHERE id = ?", (booking_id,))


def load(db, booking_id):
    return db.execute("SELECT unit_id FROM booking WHERE id = ?", (booking_id,)).fetchone()
'''
    _commit(tmp_path, {'store.py': store})
    _write(tmp_path, {'store.py': store.replace("SET note = 'closed' WHERE", "SET note = 'closed', unit_id = NULL WHERE")})
    found, _ = _impact(tmp_path)
    assert [line.text for line in found.lines] == [
        'close_day now writes booking.unit_id; 2 other writers, 1 reader of booking'], found.lines
    code, text = _flowguard(tmp_path, 'show', 'booking.unit_id', '--full')
    lines = text.splitlines()
    assert code == 0 and 'writes booking.unit_id store.py:10 close_day (sql:update)' in lines, text
    assert 'reads booking store.py:13 load (select)' in lines and 'None' not in text, text
