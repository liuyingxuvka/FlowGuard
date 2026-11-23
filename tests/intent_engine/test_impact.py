"""The impact line (design 4.6, stage 3 lane C): one `impact` line per function this change edits or adds whose
set of written fields changed, with counts and one name; `show Model.field` lists what the line counts.

Each fixture commits its baseline and edits the working tree; the lines are `owners.field_impact`'s, passed
through `signals.deliver` as lines already of their kind.
"""
from contextlib import closing
import re

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
    # The map knows the name itself, so functions that merely share a word with it wait for --full, which it says; the
    # count is what --full adds: the line that says they only share a word, and the one function.
    assert code == 0 and lines[2:] == ['const MAX_SHARE = 2 (app/limits.ts:1, app/schemas.ts:1)',
                                       '... 2 more lines, 1 of them only shares a word with MAX_SHARE: python -m flowguard '
                                       'show MAX_SHARE --full lists them all'], text
    code, text = _flowguard(tmp_path, 'show', 'MAX_SHARE', '--full')
    assert code == 0 and text.splitlines()[3:] == ['word matches: the 1 line below only shares a word with MAX_SHARE',
                                                   'typescript/app/limits.ts:shareLimit app/limits.ts:3'], text
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
        # `fte.refine((value) => value > 0)` rejects 0: the line names the refine it does not read (H1)
        f'zod key fteShare in allocationCreateSchema: 0 <= fteShare <= 2, and a refine that is not read may reject more ({allocation}:13)',
        f'zod key fteShare in batchAssignSchema: 0 <= fteShare <= 1 ({assignment}:11)',
        # `.refine(({ fteShare }) => fteShare !== 0)` of the object destructures the key: it is named too (K1)
        f'zod key fteShare in lendingUpdateSchema: 0 < fteShare <= 1, and a refine that is not read may reject more ({personnel}:9)',
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


PT_ZOD_BOUNDS_SCHEMA = """datasource db {
  provider = "sqlserver"
  url      = env("DATABASE_URL")
}

model Employee {
  id           String       @id
  sapReference Int          @map("sap_reference")
  assignments  Assignment[]
  @@map("employees")
}

model Assignment {
  id         String   @id
  employeeId String   @map("employee_id")
  employee   Employee @relation(fields: [employeeId], references: [id])
  fteShare   Decimal  @map("fte_share")
  @@map("assignments")
}

model Opportunity {
  id                   String @id
  responsibleSapNumber Int?   @map("responsible_sap_number")
  @@map("opportunities")
}

model Project {
  id          String       @id
  pspElements PspElement[]
  @@map("projects")
}

model PspElement {
  id        String  @id
  projectId String  @map("project_id")
  project   Project @relation(fields: [projectId], references: [id])
  @@map("psp_elements")
}
"""
# Planning Tool's zod schemas as its files spell them (2026-11, H1): int32 bounds held by negative constants
# (business-data-foundation.ts, personnel-mvp.schemas.ts), a z.coerce.number() constant of a query filter
# (business-data.schemas.ts), array and object keys whose nested schemas hold numbers and strings (import.schemas.ts,
# assignment.schemas.ts, central-employee.service.ts), a shared const a key narrows or refines (allocation.schemas.ts),
# a function's own schema constant and a parsed value returned under a key (project-forecast.ts), and a schema
# object written inline in a route (validateBody(z.object({...}))).
PT_ZOD_BOUNDS = {
    'backend/src/utils/business-data-foundation.ts': """import { z } from 'zod';

const MIN_SIGNED_INT32 = -2147483648;
const MAX_SIGNED_INT32 = 2147483647;
// Central personnel numbers are signed INTs, including existing negative placeholders.
const RESPONSIBLE_SAP_NUMBER_SCHEMA = z.number().finite().int()
  .min(MIN_SIGNED_INT32).max(MAX_SIGNED_INT32).nullable().optional();

export const OPPORTUNITY_CREATE_SCHEMA = z.object({
  name: z.string().trim().min(1).max(200),
  responsibleSapNumber: RESPONSIBLE_SAP_NUMBER_SCHEMA,
}).strict();
""",
    'backend/src/api/schemas/personnel-mvp.schemas.ts': """import { z } from 'zod';

/** SQL Server INT max value (2^31 - 1). */
const MIN_SAP_REFERENCE = -2_147_483_648;
const MAX_SAP_REFERENCE = 2_147_483_647;
const MIN_PLACEHOLDER = (-1);
const MAX_PLACEHOLDER = 99 as const;

const sapReferenceSchema = z.number().int()
  .min(MIN_SAP_REFERENCE, `SAP reference must not be below ${MIN_SAP_REFERENCE}.`)
  .max(MAX_SAP_REFERENCE, `SAP reference must not exceed ${MAX_SAP_REFERENCE}.`);

export const employeeCreateSchema = z.object({
  firstName: z.string().min(1).max(255),
  sapReference: sapReferenceSchema.optional(),
});

export const placeholderSchema = z.object({
  sapReference: z.number().int().min(MIN_PLACEHOLDER).max(MAX_PLACEHOLDER),
});
""",
    'backend/src/api/schemas/business-data.schemas.ts': """import { z } from 'zod';

const SAP_NUMBER = z.coerce.number().int().min(-2147483648).max(2147483647);

/** List/count filters use relation predicates rather than duplicate-producing joins. */
export const BUSINESS_LIST_SCHEMA = z.object({
  search: z.string().trim().max(200).optional(),
  responsibleSapNumber: SAP_NUMBER.optional(),
  page: z.coerce.number().int().min(1).max(100000).default(1),
}).strict();
""",
    'backend/src/api/schemas/import.schemas.ts': """import { z } from 'zod';

export const commitProjectsSchema = z.object({
  fileId: z.string().uuid('Invalid file ID.'),
  projects: z.array(z.object({
    tempId: z.string().min(1),
    pspElements: z.array(z.object({
      tempId: z.string().min(1),
      hierarchyLevel: z.number().int().min(0),
      defaultArea: z.object({
        name: z.string().min(1),
      }).nullable(),
    })),
  })).min(1),
});
""",
    'backend/src/api/schemas/assignment.schemas.ts': """import { z } from 'zod';

const MAX_BATCH_SIZE = 50;

export const batchAssignSchema = z.object({
  assignments: z
    .array(
      z.object({
        employeeId: z.string().trim().min(1, 'Employee ID is required'),
        fteShare: z.number().min(0, 'FTE share must be >= 0').max(1, 'FTE share must be <= 1'),
      }).strict(),
    )
    .min(1, 'At least one assignment is required')
    .max(MAX_BATCH_SIZE, `Maximum ${MAX_BATCH_SIZE} assignments per batch`),
}).strict();
""",
    'backend/src/services/central-employee.service.ts': """import { z } from 'zod';

const homeUnitPreviewSchema = z.object({
  purpose: z.literal('employee-home-unit-preview'),
  employee: z.object({
    id: z.string(), sapReference: z.number().int(), organizationalUnitId: z.string(),
  }),
});
""",
    'backend/src/api/schemas/allocation.schemas.ts': """import { z } from 'zod';

const fte = z.number().finite().min(0).max(2);
const shares = z.number().array();

export const allocationNarrowSchema = z.object({ fteShare: fte.max(1) }).strict();
export const allocationPositiveSchema = z.object({ fteShare: fte.gt(0).optional() }).strict();
export const allocationCreateSchema = z.object({
  fteShare: fte.refine((value) => value > 0, 'A new allocation must be greater than zero.'),
}).strict();
export const allocationRoundedSchema = z.object({
  fteShare: fte.superRefine((value, context) => undefined).transform((value) => Math.round(value * 100) / 100),
}).strict();
export const allocationSeriesSchema = z.object({ fteShare: shares }).strict();
""",
    'backend/src/utils/project-forecast.ts': """import { z } from 'zod';

const fteShare = z.number().max(9);
const projectProbabilitySchema = z.number().min(0).max(100).nullable();

/** A schema a function builds for its own range. */
export function buildAssignmentSchema(max: number) {
  const share = z.number().min(0).max(max);
  return z.object({ fteShare: share });
}

/** A parameter hides the module's constant of its name; another function's constant is not seen. */
export function wrapShare(fteShare: z.ZodTypeAny) {
  return z.object({ fteShare: fteShare });
}
export function otherSchema() {
  return z.object({ fteShare: share });
}

export function buildProjectForecast(probability: number | null, fte: number) {
  const storedProbability = projectProbabilitySchema.parse(probability);
  const fteShare = z.number().parse(fte);
  return { probability: storedProbability, fteShare: fteShare };
}
""",
    'backend/src/api/routes/allocation.routes.ts': """import { z } from 'zod';

router.post('/allocations/preview', validateBody(z.object({ fteShare: z.number().min(0).max(2) })), previewAllocation);
""",
}


def test_show_reads_a_zod_key_s_own_number_chain_with_the_constants_it_names(tmp_path):
    """Planning Tool (H1): `show Opportunity.responsibleSapNumber` printed `MIN_SIGNED_INT32 <= ... <=
    MAX_SIGNED_INT32=2147483647` (a negative constant lost its value), `show Project.pspElements` `1 <= pspElements`
    (a nested `z.string().min(1)` read as an array key's bound), `show Assignment.fteShare` `0 <= fteShare <= 2` for
    `fte.refine((value) => value > 0)` and nothing for a `z.coerce.number()` key. A zod line is now printed only for a
    key whose own schema chain is a number schema (`z.number(`, `z.coerce.number(`, directly or through a const of
    the file the key sees, a function's own const too); its bounds are the const's chain with the key's chain after
    it, a later bound replacing an earlier one of the same side; a numeric const keeps its value as spelled; a
    refine, superRefine or transform is named, not read."""
    _commit(tmp_path, {'backend/prisma/schema.prisma': PT_ZOD_BOUNDS_SCHEMA, **PT_ZOD_BOUNDS})

    def zod(query):
        code, text = _flowguard(tmp_path, 'show', query)
        assert code == 0 and 'not on the map' not in text, text
        return [line for line in text.splitlines() if line.startswith('zod')]
    foundation, personnel, business, allocation, forecast, routes = (
        'backend/src/utils/business-data-foundation.ts', 'backend/src/api/schemas/personnel-mvp.schemas.ts',
        'backend/src/api/schemas/business-data.schemas.ts', 'backend/src/api/schemas/allocation.schemas.ts',
        'backend/src/utils/project-forecast.ts', 'backend/src/api/routes/allocation.routes.ts')
    # (gate-3) the schema objects named after the model come first, then those that share the key's name only
    assert zod('Opportunity.responsibleSapNumber') == [
        'zod key responsibleSapNumber in OPPORTUNITY_CREATE_SCHEMA: MIN_SIGNED_INT32=-2147483648 <= responsibleSapNumber'
        f' <= MAX_SIGNED_INT32=2147483647 ({foundation}:11)',
        f'zod key responsibleSapNumber in BUSINESS_LIST_SCHEMA: -2147483648 <= responsibleSapNumber <= 2147483647 ({business}:8)']
    # a negative, parenthesised or `as const` constant keeps its value as spelled; a nested number key of an object
    # key is a line of its own, under the object it belongs to
    assert zod('Employee.sapReference') == [
        f'zod key sapReference in employeeCreateSchema: MIN_SAP_REFERENCE=-2_147_483_648 <= sapReference <= MAX_SAP_REFERENCE=2_147_483_647 ({personnel}:15)',
        'zod key sapReference in employee: sapReference (no bounds) (backend/src/services/central-employee.service.ts:6)',
        f'zod key sapReference in placeholderSchema: MIN_PLACEHOLDER=-1 <= sapReference <= MAX_PLACEHOLDER=99 ({personnel}:19)']
    # an array or object key is no number: the bounds of its nested schemas and its length are not its bounds
    assert zod('Project.pspElements') == zod('Employee.assignments') == zod('Assignment.employee') == []
    assert zod('Assignment.fteShare') == [
        f'zod key fteShare in an unnamed object: 0 <= fteShare <= 2 ({routes}:3)',
        f'zod key fteShare in allocationNarrowSchema: 0 <= fteShare <= 1 ({allocation}:6)',
        f'zod key fteShare in allocationPositiveSchema: 0 < fteShare <= 2 ({allocation}:7)',
        f'zod key fteShare in allocationCreateSchema: 0 <= fteShare <= 2, and a refine that is not read may reject more ({allocation}:9)',
        f'zod key fteShare in allocationRoundedSchema: 0 <= fteShare <= 2, and a superRefine and a transform that are '
        f'not read may reject more ({allocation}:12)',
        'zod key fteShare in batchAssignSchema: 0 <= fteShare <= 1 (backend/src/api/schemas/assignment.schemas.ts:10)',
        # a function's own const; a parameter of the name hides the module's const, a parsed value is no schema
        f'zod key fteShare in an unnamed object: 0 <= fteShare <= max ({forecast}:9)']


def test_show_of_a_field_its_known_model_lacks_lists_no_zod_key_and_says_so(tmp_path):
    """Planning Tool (H1): `show Employee.fteShare` printed ten `zod key fteShare in ...` lines and nothing else of
    the field, though neither the Prisma model Employee nor the TS interface Employee has one, and held every
    word-matched line back for --full as if the map knew the name. A field the Prisma models and SQL tables of a
    known model lack (and its TS types: a member, or members not all read, counts as having it) now gets no zod
    line and a `not on the map` line saying so; the model's other names keep their lines: a SQL table, a Prisma
    `@@map` table and a class of the map are known models (`owners.model_known`)."""
    _commit(tmp_path, {
        'backend/prisma/schema.prisma': """datasource db {
  provider = "sqlserver"
  url      = env("DATABASE_URL")
}

model Employee {
  id           String @id
  sapReference Int    @map("sap_reference")
  @@map("employees")
}

model Assignment {
  id       String  @id
  fteShare Decimal @map("fte_share")
  @@map("assignments")
}

model Demand {
  id String @id
  @@map("demands")
}

model LendingAssignment {
  id String @id
  @@map("lending_assignments")
}
""",
        'backend/prisma/capacity-setup.sql': """CREATE TABLE capacity_bookings (
  id NVARCHAR(36) PRIMARY KEY,
  fte_share DECIMAL(6,4) NOT NULL CHECK (fte_share >= 0 AND fte_share <= 2)
);
""",
        'backend/src/api/schemas/allocation.schemas.ts': """import { z } from 'zod';

export const allocationCreateSchema = z.object({ fteShare: z.number().min(0).max(2) }).strict();
export const capacityImportRowSchema = z.object({ fte_share: z.coerce.number().min(0).max(2) });
""",
        'frontend/src/types/domain.types.ts': """export interface Employee {
  id: string;
  sapReference: number;
}

export interface Demand {
  id: string;
  fteShare: number;
}

export interface LendingAssignment extends AssignmentBase {
  id: string;
}
""",
        'frontend/src/utils/add-project-quantity.ts': 'export function roundFteShare(value: number): number { return Math.round(value * 100) / 100; }\n',
        'tools/capacity_report.py': 'class CapacityRow:\n    fteShare = 0.0\n',
    })

    def shown(query):
        code, text = _flowguard(tmp_path, 'show', query)
        assert code == 0, text
        return text.splitlines()
    zod = 'zod key fteShare in allocationCreateSchema: 0 <= fteShare <= 2 (backend/src/api/schemas/allocation.schemas.ts:3)'
    lines = shown('Employee.fteShare')
    assert not [line for line in lines if line.startswith('zod')], lines
    assert lines[2] == ('not on the map: Prisma model Employee and TS type Employee have no field fteShare; the zod keys '
                        'fteShare of 1 schema object are not listed, as a key matches by its name alone; Prisma models '
                        'with a field fteShare: Assignment'), lines
    # no line claims the map knows the name: the functions that share a word with it are listed, not held for --full
    assert any('roundFteShare' in line for line in lines) and not any('more lines' in line for line in lines), lines
    # a TS type of the name with the member, or one that extends another, counts as having it
    for query in ('Demand.fteShare', 'LendingAssignment.fteShare', 'assignments.fteShare', 'CapacityRow.fteShare'):
        lines = shown(query)
        assert zod in lines and not any(line.startswith('not on the map') for line in lines), (query, lines)
    # a SQL table no Prisma model maps: its column, CHECK range and zod key; a column it lacks is said so
    lines = shown('capacity_bookings.fte_share')
    # (gate-3) capacityImportRowSchema is not named after capacity_bookings: a line says its key matches by the name only
    assert lines[2:6] == ['column capacity_bookings.fte_share DECIMAL(6,4) (backend/prisma/capacity-setup.sql:3)',
                          'range capacity_bookings.fte_share: 0 <= fte_share <= 2 (CHECK backend/prisma/capacity-setup.sql:3)',
                          'the zod line below is a key of the same name in another schema object, matched by the name only',
                          'zod key fte_share in capacityImportRowSchema: 0 <= fte_share <= 2 (backend/src/api/schemas/allocation.schemas.ts:4)'], lines
    assert not any(line.startswith('not on the map') for line in lines), lines
    assert shown('capacity_bookings.fte_ratio')[2] == 'not on the map: database table capacity_bookings has no column fte_ratio'


PT_ZOD_CHECKS_SCHEMA = """datasource db {
  provider = "sqlserver"
  url      = env("DATABASE_URL")
}

model Assignment {
  id       String  @id
  fteShare Decimal @map("fte_share")
  @@map("assignments")
}

model CapacityCalendarEntry {
  id       String @id
  value    Float
  unitType String @map("unit_type")
  @@map("capacity_calendar_entries")
}
"""
# Planning Tool's zod spellings (2026-11, K1): a shared constant a key narrows, widens or bounds by an imported
# name (allocation.schemas.ts), a query key coerced and piped, the wrappers z.optional, z.nullable, z.nullish and
# z.preprocess, a function's own `let` and a loop variable or catch parameter of the module constant's name
# (project-forecast.ts), and the object refines of capacityEntryCreateSchema (personnel-mvp.schemas.ts:198-216): one
# whose path and destructuring name the key, one of another key, a superRefine adding an issue at the key's path.
PT_ZOD_CHECKS = {
    'backend/src/api/schemas/allocation.schemas.ts': """import { z } from 'zod';
import { MAX_IMPORTED_SHARE, MIN_IMPORTED_SHARE } from '../../utils/share-limits';

const MAX_FTE_SHARE = 2.0;
const fte = z.number().finite().min(0).max(MAX_FTE_SHARE);

export const allocationLooseSchema = z.object({ fteShare: fte.max(3) }).strict();
export const allocationNarrowSchema = z.object({ fteShare: fte.max(1) }).strict();
export const allocationBelowSchema = z.object({ fteShare: fte.lt(2) }).strict();
export const allocationPositiveSchema = z.object({ fteShare: z.number().min(0.1).positive() }).strict();
export const allocationImportedSchema = z.object({ fteShare: fte.max(MAX_IMPORTED_SHARE) }).strict();
export const allocationFloorSchema = z.object({ fteShare: z.number().min(MIN_IMPORTED_SHARE).min(0) }).strict();
export const allocationQuerySchema = z.object({
  fteShare: z.coerce.number().pipe(z.number().min(0).max(2)),
}).strict();
export const allocationPipedSchema = z.object({ fteShare: z.number().min(0).max(5).pipe(z.number().max(3)) }).strict();
export const allocationTextSchema = z.object({ fteShare: z.string().pipe(z.coerce.number()) }).strict();
export const allocationOptionalSchema = z.object({ fteShare: z.optional(z.number().min(0)) }).strict();
export const allocationNullableSchema = z.object({ fteShare: z.nullable(fte.max(1)) }).strict();
export const allocationNullishSchema = z.object({ fteShare: z.nullish(z.number().gt(0)) }).strict();
export const allocationFormSchema = z.object({
  fteShare: z.preprocess((value) => (value === '' ? undefined : Number(value)), z.number().min(0).max(9)),
}).strict();
""",
    'backend/src/utils/project-forecast.ts': """import { z } from 'zod';

const share = z.number().max(1);

/** A function's own `let` holds its schema; a loop variable and a catch parameter hide the module's constant. */
export function buildDraftSchema() {
  let share = z.number().max(9);
  return z.object({ fteShare: share });
}

export function firstShare(list: number[]) {
  for (const share of list) {
    return { fteShare: share };
  }
  return null;
}

export function recoveredShare() {
  try { return null; } catch (share) { return { fteShare: share }; }
}
""",
    'backend/src/api/schemas/personnel-mvp.schemas.ts': """import { z } from 'zod';
import { MAX_CAPACITY_PERCENT } from '../../utils/capacity-limits';

const MAX_CAPACITY_HOURS = 24;
const dateRangeBaseSchema = z.object({ startDate: z.string(), endDate: z.string() });

export const capacityEntryCreateSchema = dateRangeBaseSchema
  .extend({
    value: z.number().min(0, 'Capacity value must be non-negative.').max(MAX_CAPACITY_HOURS, `Capacity value cannot exceed ${MAX_CAPACITY_HOURS}h per day.`),
    unitType: z.enum(['HOURS', 'PERCENT']),
  })
  .refine(({ startDate, endDate }) => startDate <= endDate, {
    path: ['endDate'],
    message: 'endDate must be greater than or equal to startDate.',
  })
  .refine(
    ({ value, unitType }) => unitType !== 'PERCENT' || value <= MAX_CAPACITY_PERCENT,
    { path: ['value'], message: `Percent value cannot exceed ${MAX_CAPACITY_PERCENT * 100}%.` },
  );

export const capacityEntryUpdateSchema = dateRangeBaseSchema
  .partial()
  .extend({ value: z.number().min(0).optional(), unitType: z.enum(['HOURS', 'PERCENT']).optional() })
  .refine(({ startDate, endDate }) => !startDate || !endDate || startDate <= endDate, {
    path: ['endDate'],
    message: 'endDate must be greater than or equal to startDate.',
  });

export const capacityImportRowSchema = z.object({
  value: z.coerce.number().min(0).max(MAX_CAPACITY_HOURS),
  unitType: z.string(),
}).superRefine((row, context) => {
  if (row.unitType === 'PERCENT' && row.value > MAX_CAPACITY_PERCENT) {
    context.addIssue({ code: z.ZodIssueCode.custom, path: ['value'], message: 'Percent value above the limit.' });
  }
});

export const capacityListQuerySchema = z.object({
  value: z.coerce.number().min(0).optional(),
}).refine((query) => query.value !== 7, { message: 'A week has no eighth day.' });
""",
}


def test_show_reads_every_check_of_a_zod_number_chain_zod_runs(tmp_path):
    """Planning Tool (K1): zod runs every check of a key's chain, and the lines dropped some. `fte.max(3)` of
    `const fte = z.number().min(0).max(2)` printed `<= 3`, as if the later bound replaced the earlier, where zod
    rejects 2.5; `z.coerce.number().pipe(z.number().min(0).max(2))` printed `(no bounds)`, `.pipe(z.number().max(3))`
    after `.max(5)` printed `<= 5`; `z.optional(...)`, `z.nullable(...)`, `z.nullish(...)` and `z.preprocess(fn,
    ...)` printed nothing; a function's `let share` read the module's `const share`, and so did a `for (const share
    of ...)` variable and a `catch (share)` parameter, in plain objects; and capacityEntryCreateSchema's value line
    said nothing of the object refine at `path: ['value']` that rejects PERCENT values above 3. Now the stricter of
    two bounds of one side holds where the line can compare them (numbers, a const with its value) and one it cannot
    compare stays beside the other; wrappers and both schemas of a pipe are read; those bindings hide the module
    constant; an object refine (or superRefine) that destructures the key or names it as its path is named on the
    key's line, another adds nothing."""
    _commit(tmp_path, {'backend/prisma/schema.prisma': PT_ZOD_CHECKS_SCHEMA, **PT_ZOD_CHECKS})

    def zod(query):
        code, text = _flowguard(tmp_path, 'show', query)
        assert code == 0 and 'not on the map' not in text, text
        return [line for line in text.splitlines() if line.startswith('zod')]
    allocation, personnel, forecast = ('backend/src/api/schemas/allocation.schemas.ts',
                                       'backend/src/api/schemas/personnel-mvp.schemas.ts', 'backend/src/utils/project-forecast.ts')
    assert zod('Assignment.fteShare') == [
        f'zod key fteShare in allocationLooseSchema: 0 <= fteShare <= MAX_FTE_SHARE=2.0 ({allocation}:7)',
        f'zod key fteShare in allocationNarrowSchema: 0 <= fteShare <= 1 ({allocation}:8)',
        f'zod key fteShare in allocationBelowSchema: 0 <= fteShare < 2 ({allocation}:9)',
        f'zod key fteShare in allocationPositiveSchema: 0.1 <= fteShare ({allocation}:10)',
        f'zod key fteShare in allocationImportedSchema: 0 <= fteShare <= MAX_FTE_SHARE=2.0 and <= MAX_IMPORTED_SHARE ({allocation}:11)',
        f'zod key fteShare in allocationFloorSchema: MIN_IMPORTED_SHARE <= fteShare and >= 0 ({allocation}:12)',
        f'zod key fteShare in allocationQuerySchema: 0 <= fteShare <= 2 ({allocation}:14)',
        f'zod key fteShare in allocationPipedSchema: 0 <= fteShare <= 3 ({allocation}:16)',
        # a string piped into a number is no number schema: allocationTextSchema has no line
        f'zod key fteShare in allocationOptionalSchema: 0 <= fteShare ({allocation}:18)',
        f'zod key fteShare in allocationNullableSchema: 0 <= fteShare <= 1 ({allocation}:19)',
        f'zod key fteShare in allocationNullishSchema: 0 < fteShare ({allocation}:20)',
        f'zod key fteShare in allocationFormSchema: 0 <= fteShare <= 9 ({allocation}:22)',
        f'zod key fteShare in an unnamed object: fteShare <= 9 ({forecast}:8)']
    assert zod('CapacityCalendarEntry.value') == [
        f'zod key value in capacityEntryCreateSchema: 0 <= value <= MAX_CAPACITY_HOURS=24, and a refine that is not read '
        f'may reject more ({personnel}:9)',
        f'zod key value in capacityEntryUpdateSchema: 0 <= value ({personnel}:23)',
        f'zod key value in capacityImportRowSchema: 0 <= value <= MAX_CAPACITY_HOURS=24, and a superRefine that is not '
        f'read may reject more ({personnel}:30)',
        f'zod key value in capacityListQuerySchema: 0 <= value ({personnel}:39)']


PT_ZOD_PIPES = {
    'backend/src/api/schemas/share.ts': "import { z } from 'zod';\nexport const fteShareSchema = z.number().max(2);\n",
    'backend/src/api/schemas/allocation.schemas.ts': """import { z } from 'zod';
import { fteShareSchema } from './share';

const localShare = z.number().max(1);

export const allocationImportSchema = z.object({
  fteShare: z.coerce.number().min(0).pipe(fteShareSchema),
}).strict();
export const allocationDoubledSchema = z.object({
  fteShare: z.number().min(0).pipe(z.transform((value: number) => value * 2)),
}).strict();
export const allocationLocalSchema = z.object({ fteShare: z.number().min(0).pipe(localShare) }).strict();
""",
}


def test_a_pipe_into_a_schema_the_reader_cannot_read_keeps_the_key_s_bounds_and_names_the_pipe(tmp_path):
    """K1-0 (2026-11): reading both schemas of `X.pipe(Y)` made a Y the reader cannot read (a schema imported from
    another file, `z.transform(fn)`) drop the key's whole zod line, so `show` said nothing of the key's own bounds and
    nothing of why. X's bounds stay and the line names the pipe as it names a transform: not read, it may reject
    more; a pipe into a same-file const is still read."""
    _commit(tmp_path, {'backend/prisma/schema.prisma': PT_ZOD_CHECKS_SCHEMA, **PT_ZOD_PIPES})
    code, text = _flowguard(tmp_path, 'show', 'Assignment.fteShare')
    allocation = 'backend/src/api/schemas/allocation.schemas.ts'
    assert code == 0 and [line for line in text.splitlines() if line.startswith('zod')] == [
        f'zod key fteShare in allocationImportSchema: 0 <= fteShare, and a pipe that is not read may reject more ({allocation}:7)',
        f'zod key fteShare in allocationDoubledSchema: 0 <= fteShare, and a transform that is not read may reject more ({allocation}:10)',
        f'zod key fteShare in allocationLocalSchema: 0 <= fteShare <= 1 ({allocation}:12)'], text


def test_show_of_a_sql_table_reads_its_columns_as_the_columns_check_does(tmp_path):
    """Planning Tool shape (K1): a SQL-only table whose Prisma-generated SQLite migration rebuilds it
    (`CREATE TABLE "new_t"`, `DROP TABLE "t"`, `ALTER TABLE "new_t" RENAME TO "t"`) got `not on the map: database
    table capacity_bookings has no column note` for the column the rebuild adds, and its zod key was withheld, while
    the column the rebuild drops still counted. The columns now are those the columns check reads (`sql.describe`),
    and an upgrade script's ALTER ADD of the table (docs/releases/.../app_database_upgrade.sql) still counts."""
    _commit(tmp_path, {
        'backend/prisma/schema.prisma': PT_ZOD_CHECKS_SCHEMA,
        'backend/prisma/migrations/20260317073846_init/migration.sql': """CREATE TABLE "capacity_bookings" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "share" DECIMAL NOT NULL,
    "legacy_code" INTEGER
);
""",
        'backend/prisma/migrations/20260331085358_add_booking_note/migration.sql': """-- RedefineTables
PRAGMA defer_foreign_keys=ON;
PRAGMA foreign_keys=OFF;
CREATE TABLE "new_capacity_bookings" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "share" DECIMAL NOT NULL,
    "note" INTEGER NOT NULL DEFAULT 0
);
INSERT INTO "new_capacity_bookings" ("id", "share") SELECT "id", "share" FROM "capacity_bookings";
DROP TABLE "capacity_bookings";
ALTER TABLE "new_capacity_bookings" RENAME TO "capacity_bookings";
PRAGMA foreign_keys=ON;
PRAGMA defer_foreign_keys=OFF;
""",
        'docs/releases/azure-production-candidate/app_database_upgrade.sql': """IF COL_LENGTH(N'dbo.capacity_bookings', N'fte_ratio') IS NULL
  ALTER TABLE [dbo].[capacity_bookings] ADD [fte_ratio] DECIMAL(6,4) NULL;
""",
        'backend/src/api/schemas/booking.schemas.ts': """import { z } from 'zod';

export const bookingSchema = z.object({ note: z.number().min(0), fte_ratio: z.number().max(2), legacy_code: z.number().int() });
""",
    })

    def shown(query):
        code, text = _flowguard(tmp_path, 'show', query)
        assert code == 0, text
        return text.splitlines()
    schemas = 'backend/src/api/schemas/booking.schemas.ts'
    for query, line in (('capacity_bookings.note', f'zod key note in bookingSchema: 0 <= note ({schemas}:3)'),
                        ('capacity_bookings.fte_ratio', f'zod key fte_ratio in bookingSchema: fte_ratio <= 2 ({schemas}:3)')):
        lines = shown(query)
        assert line in lines and not any(item.startswith('not on the map') for item in lines), (query, lines)
    assert shown('capacity_bookings.legacy_code')[2] == (
        'not on the map: database table capacity_bookings has no column legacy_code; the zod keys legacy_code of 1 '
        'schema object are not listed, as a key matches by its name alone')


PT_DEMAND_SCHEMA = """datasource db {
  provider = "sqlserver"
  url      = env("DATABASE_URL")
}

model Demand {
  id           String @id
  pspElementId Int?   @map("psp_element_id")
  hoursPlanned Float  @map("hours_planned")
  @@map("demands")
}
"""
PT_DEMAND_INIT = """CREATE TABLE "demands" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "psp_element_id" TEXT,
    "planned_hours" REAL NOT NULL
);
"""


def test_a_column_line_gives_the_type_the_migrations_leave_after_their_rebuilds(tmp_path):
    """pt-smoke-1 (2026-11): on Planning Tool `show Demand.pspElementId` printed `column demands.psp_element_id TEXT
    (backend/prisma/migrations/20260317073846_init/migration.sql:163, docs/database-history/.../migration.sql:163)`,
    the init migration's type, although the SQLite rebuilds of 20260325091829_psp_element_int_ids (`CREATE TABLE
    "new_demands"` ... `ALTER TABLE "new_demands" RENAME TO "demands"`) leave it INTEGER. A column line now gives the
    type each description the columns check reads ends with, at its last declaration: the migrations folder as one,
    a RENAME COLUMN keeping its type, and the archive under docs/ left out as that check leaves it out."""
    rebuild = """-- RedefineTables
PRAGMA foreign_keys=OFF;
CREATE TABLE "new_demands" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "psp_element_id" INTEGER,
    "planned_hours" REAL NOT NULL
);
INSERT INTO "new_demands" ("id", "psp_element_id", "planned_hours") SELECT "id", "psp_element_id", "planned_hours" FROM "demands";
DROP TABLE "demands";
ALTER TABLE "new_demands" RENAME TO "demands";
PRAGMA foreign_keys=ON;
"""
    _commit(tmp_path, {
        'backend/prisma/schema.prisma': PT_DEMAND_SCHEMA,
        'backend/prisma/azure-sql-setup.sql': 'CREATE TABLE demands (\n  id NVARCHAR(36) NOT NULL,\n  psp_element_id INT NULL,\n'
                                              '  hours_planned FLOAT NOT NULL\n);\n',
        'backend/prisma/migrations/20260317073846_init/migration.sql': PT_DEMAND_INIT,
        'backend/prisma/migrations/20260325091829_psp_element_int_ids/migration.sql': rebuild,
        'backend/prisma/migrations/20260401090000_rename_hours/migration.sql':
            'ALTER TABLE "demands" RENAME COLUMN "planned_hours" TO "hours_planned";\n',
        'docs/database-history/main-a956b33f/backend/prisma/migrations/20260317073846_init/migration.sql': PT_DEMAND_INIT,
    })

    def columns(query):
        code, text = _flowguard(tmp_path, 'show', query)
        assert code == 0, text
        return [line for line in text.splitlines() if line.startswith('column ')]
    assert columns('Demand.pspElementId') == [
        'column demands.psp_element_id INT (backend/prisma/azure-sql-setup.sql:3)',
        'column demands.psp_element_id INTEGER (backend/prisma/migrations/20260325091829_psp_element_int_ids/migration.sql:5)']
    assert columns('Demand.hoursPlanned') == [
        'column demands.hours_planned FLOAT (backend/prisma/azure-sql-setup.sql:4)',
        'column demands.hours_planned REAL (backend/prisma/migrations/20260401090000_rename_hours/migration.sql:1)']


PT_ASSIGNMENT_SCHEMA = """datasource db {
  provider = "sqlserver"
  url      = env("DATABASE_URL")
}

model Assignment {
  id              String  @id
  demandId        String? @map("demand_id")
  internalOrderId String? @map("internal_order_id")
  @@map("assignments")
}
"""
PT_ASSIGNMENT_INIT = 'CREATE TABLE "assignments" (\n    "id" TEXT NOT NULL PRIMARY KEY,\n    "demand_id" TEXT NOT NULL\n);\n'


def test_a_column_line_reads_an_alter_column_type_and_no_sql_a_string_builds(tmp_path):
    """Planning Tool (2026-11): pt-smoke-1's column lines missed an ALTER COLUMN (Z-4): `show Assignment.demandId` said
    `column assignments.demand_id TEXT (.../20260317073846_init/migration.sql:183)` although
    20260410120000_add_partial_forward_fields/migration.sql:80 is `ALTER TABLE [assignments] ALTER COLUMN [demand_id]
    NVARCHAR(36) NULL;`. The SQL reader also read the ALTER inside a T-SQL string (Z-5): `show
    Assignment.internalOrderId` printed `column assignments.internal_order_id '` from `SET @sql = N'ALTER TABLE
    [dbo].[assignments] ADD [internal_order_id] ' + @technicalType + N' NULL;'`. And `show Employee` listed the table
    lines of the docs/database-history archives the column lines and the columns check leave out (Z-8). An ALTER COLUMN
    that gives a type (T-SQL, or Postgres `TYPE`) declares it; SQL built in a string at run time declares nothing, so
    the migrations folder lacks that column; an archive gives no table line."""
    dynamic = """DECLARE @technicalType NVARCHAR(64) = N'NVARCHAR(36)';
DECLARE @sql NVARCHAR(MAX);
IF COL_LENGTH(N'dbo.assignments', N'internal_order_id') IS NULL
BEGIN
    SET @sql = N'ALTER TABLE [dbo].[assignments] ADD [internal_order_id] ' + @technicalType + N' NULL;';
    EXEC sys.sp_executesql @sql;
END;
"""
    _commit(tmp_path, {
        'backend/prisma/schema.prisma': PT_ASSIGNMENT_SCHEMA,
        'backend/prisma/migrations/20260317073846_init/migration.sql': PT_ASSIGNMENT_INIT,
        'backend/prisma/migrations/20260410120000_add_partial_forward_fields/migration.sql':
            'ALTER TABLE [assignments] ALTER COLUMN [demand_id] NVARCHAR(36) NULL;\n',
        'backend/prisma/migrations/20261012120000_opportunity_internal_order_foundation/migration.sql': dynamic,
        'backend/prisma/postgres-setup.sql': ('CREATE TABLE "assignments" ("id" TEXT NOT NULL, "demand_id" TEXT, '
                                              '"internal_order_id" TEXT);\nALTER TABLE "assignments" ALTER COLUMN "demand_id" '
                                              'SET NOT NULL, ALTER COLUMN "demand_id" TYPE VARCHAR(36);\n'),
        'docs/database-history/main-a956b33f/backend/prisma/migrations/20260317073846_init/migration.sql': PT_ASSIGNMENT_INIT,
    })

    def shown(query, start):
        code, text = _flowguard(tmp_path, 'show', query)
        assert code == 0, text
        return [line for line in text.splitlines() if line.startswith(start)]
    assert shown('Assignment.demandId', 'column ') == [
        'column assignments.demand_id NVARCHAR(36) (backend/prisma/migrations/20260410120000_add_partial_forward_fields/'
        'migration.sql:1)',
        'column assignments.demand_id VARCHAR(36) (backend/prisma/postgres-setup.sql:2)']
    assert shown('Assignment.internalOrderId', 'column ') == [
        'column assignments.internal_order_id TEXT (backend/prisma/postgres-setup.sql:1)']
    assert shown('Assignment', 'table ') == [
        'table assignments: 2 columns (backend/prisma/migrations/ as its migrations leave it, created at '
        'backend/prisma/migrations/20260317073846_init/migration.sql:1)',
        'table assignments: 3 columns (backend/prisma/postgres-setup.sql:1)']
    # The columns check reads the same: the migrations folder lacks the column only a string adds.
    code, text = _flowguard(tmp_path, 'check', '--static', '--all')
    assert code == 0 and text.splitlines()[1:] == [
        'before: columns migrations/ against backend/prisma/schema.prisma at migrations/ was broken at task start -> '
        'leave it unless your task is about it'], text
    with closing(build(tmp_path, workers=1)) as graph:
        assert [(gap['description'], gap['table'], gap['missing']) for gap in graph.schema_gaps()] == [
            ('backend/prisma/migrations/', 'assignments', ['internal_order_id'])]


def test_the_anchor_view_of_a_field_its_known_model_lacks_says_so_before_its_facts(tmp_path):
    """The ANCHOR view (a field an agreement names) prints the `not on the map` line too, after the agreement's lines
    and before the field's facts: a together agreement on Employee.fteShare, a field neither the Prisma model Employee nor the TS interface
    Employee has (K1: no test held this line; dropping it from the ANCHOR facts passed every test)."""
    _commit(tmp_path, {
        'backend/prisma/schema.prisma': PT_ZOD_CHECKS_SCHEMA + """
model Employee {
  id           String @id
  sapReference Int    @map("sap_reference")
  @@map("employees")
}
""",
        'frontend/src/types/domain.types.ts': 'export interface Employee {\n  id: string;\n  sapReference: number;\n}\n',
        'backend/src/api/schemas/allocation.schemas.ts': """import { z } from 'zod';

export const allocationCreateSchema = z.object({ fteShare: z.number().min(0).max(2) }).strict();
""",
        'backend/src/services/fte.service.ts': """// flowguard: together Employee.fteShare Assignment.fteShare on=update
export async function setShare(prisma: any, id: string, share: number) {
  await prisma.employee.update({ where: { id }, data: { fteShare: share } });
  await prisma.assignment.updateMany({ where: { employeeId: id }, data: { fteShare: share } });
}
""",
    })
    code, text = _flowguard(tmp_path, 'show', 'Employee.fteShare')
    lines = text.splitlines()
    assert code == 0 and lines[0] == 'show Employee.fteShare' and lines[1].startswith('Map: '), text
    absent = ('not on the map: Prisma model Employee and TS type Employee have no field fteShare; the zod keys fteShare '
              'of 1 schema object are not listed, as a key matches by its name alone; Prisma models with a field '
              'fteShare: Assignment')
    # after the agreement's line, before the field's writes
    at = lines.index(absent)
    assert lines.count(absent) == 1 and lines[at - 1].startswith('together Employee.fteShare Assignment.fteShare on=update ') \
        and lines[at + 1].startswith('writes Employee.fteShare '), text
    assert not any(line.startswith('zod') for line in lines), text


def test_show_of_an_anchored_field_cuts_its_facts_to_the_screen_and_full_lists_them(tmp_path):
    """Planning Tool (H1): `show Employee.sapReference`, which a together agreement anchors, printed 50 lines ending
    with `... 21 more lines: python -m flowguard show Employee.sapReference --full lists them all`; no test had more
    facts than the screen holds. The ANCHOR view cuts the field's declaration, zod and write lines to `screen_lines`
    and says how many --full adds; --full lists them all."""
    seeds = ''.join(f"""  await prisma.employee.upsert({{ where: {{ id: 'e{number}' }}, update: {{}},
    create: {{ id: 'e{number}', sapReference: {1000 + number} }} }});
""" for number in range(1, 6))
    _commit(tmp_path, {
        'pyproject.toml': '[tool.flowguard]\nscreen_lines = 4\n',
        'backend/prisma/schema.prisma': PT_ZOD_BOUNDS_SCHEMA,
        'backend/prisma/seed.ts': f'export async function main(prisma: any) {{\n{seeds}}}\n',
        'backend/src/services/sap-number-renumber.service.ts': """// flowguard: together Employee.sapReference Opportunity.responsibleSapNumber on=update
export async function renumberSapNumber(prisma: any, id: string, oldNumber: number, newNumber: number) {
  await prisma.employee.update({ where: { id }, data: { sapReference: newNumber } });
  await prisma.opportunity.updateMany({ where: { responsibleSapNumber: oldNumber }, data: { responsibleSapNumber: newNumber } });
}
""",
    })
    writes = [f'writes Employee.sapReference backend/prisma/seed.ts:{3 + 2 * number} (call line {2 + 2 * number}) main (upsert:create)'
              for number in range(5)]
    facts = ['declared Employee.sapReference: Int @map("sap_reference") (backend/prisma/schema.prisma:8)', *writes,
             'writes Employee.sapReference backend/src/services/sap-number-renumber.service.ts:3 renumberSapNumber (update)']
    code, text = _flowguard(tmp_path, 'show', 'Employee.sapReference')
    lines = text.splitlines()
    assert code == 0 and lines[0] == 'show Employee.sapReference' and lines[1].startswith('Map: '), text
    start = lines.index(facts[0])
    assert lines[start:start + 4] == [*facts[:3], '... 4 more lines: python -m flowguard show Employee.sapReference --full lists them all'], text
    code, text = _flowguard(tmp_path, 'show', 'Employee.sapReference', '--full')
    lines = text.splitlines()
    start = lines.index(facts[0])
    assert code == 0 and lines[start:start + len(facts)] == facts and 'more lines' not in text, text


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
        # a test's byte-identical copy of a production interface: the map reads one set declared by both files
        'backend/tests/unit/row.test.ts': "interface PlanRow { action: 'read' | 'write' }\nexport const rows: PlanRow[] = [];\n",
        # a production file whose name starts with test_ is a test file for the map, whatever its language
        'frontend/src/constants/test_ids.ts': "export const STATUS_LABELS = ['Open', 'Done'] as const;\nexport const MAX_IDS = 10;\n",
        'frontend/src/constants/paging.ts': 'export const PAGE_SIZE = 25;\n',
    })
    def shown(name):
        code, text = _flowguard(tmp_path, 'show', name)
        assert code == 0, text
        return [line for line in text.splitlines() if line.startswith(('const ', 'values '))]
    cfg = load_config(tmp_path)
    with closing(build(tmp_path, roots=cfg.roots)) as graph:
        assert [row['scope'] for row in graph.value_sets() if row['name'] == 'PlanRow.action'] == [
            ('app/row.ts', 'backend/tests/unit/row.test.ts')]
    assert shown('MAX_ROWS') == ['const MAX_ROWS = 10 (app/limits.ts:1)']
    assert shown('AccessKind') == ['values AccessKind: read | write (app/limits.ts:2)']
    assert shown('PlanRow.action') == ['values PlanRow.action: read | write (app/row.ts:1)']      # a production file declares it too
    assert shown('ROLES') == shown('STEPS') == shown('AccessRow.action') == []
    assert shown('PAGE_SIZE') == ['const PAGE_SIZE = 25 (frontend/src/constants/paging.ts:1)']
    assert shown('MAX_IDS') == shown('STATUS_LABELS') == []


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
export async function changeEmployeeHomeUnit(prisma: any, central: any, id: string, centralId: string, unit: string) {
  await prisma.employee.updateMany({ where: { id }, data: { organizationalUnitId: unit } });
  await central.centralEmployee.updateMany({ where: { id: centralId }, data: { orgUnitId: unit } });
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
    assert code == 0 and lines[0] == 'show CentralEmployee.orgUnitId' and lines[1].startswith('Map: ') and lines[3].startswith(
        'together CentralEmployee.orgUnitId'), text
    facts = lines[4:8]          # the agreement holds (the two updates select their own records): no fix line
    assert not [line for line in lines if line.startswith(('missing ', 'fix: '))], text
    assert facts == [
        'declared CentralEmployee.orgUnitId: String? @map("org_unit_id") (backend/prisma/central/schema.prisma:8)',
        'column central_employees.org_unit_id TEXT (backend/prisma/central/migrations/20260330131802_init_central_org/migration.sql:3)',
        'writes CentralEmployee.orgUnitId backend/prisma/migrate-to-central.ts:2 migrateEmployees (create)',
        'writes CentralEmployee.orgUnitId backend/src/services/employee-home-unit.service.ts:4 changeEmployeeHomeUnit (updateMany)'], text
    code, text = _flowguard(tmp_path, 'show', 'Project.lifecycleStatusId')
    lines = text.splitlines()
    assert code == 0 and lines[0] == 'show Project.lifecycleStatusId' and lines[1].startswith('Map: '), text
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


PT_PAIRS_SCHEMA = """datasource db {
  provider = "sqlserver"
  url      = env("DATABASE_URL")
}

model Employee {
  id           String @id
  sapReference Int    @map("sap_reference")
  @@map("employees")
}

model Opportunity {
  id                   String @id
  responsibleSapNumber Int?   @map("responsible_sap_number")
  @@map("opportunities")
}

model Project {
  id       String          @id
  leaderId String          @map("leader_id")
  members  ProjectMember[]
  @@map("projects")
}

model ProjectMember {
  id         String  @id
  projectId  String  @map("project_id")
  project    Project @relation(fields: [projectId], references: [id])
  employeeId String  @map("employee_id")
  role       String
  @@map("project_members")
}
"""


def test_show_of_a_together_field_marks_the_writes_that_miss_a_partner_and_prints_the_fix_only_then(tmp_path):
    """Planning Tool (5.0 review, pt:F5): the ANCHOR view of a together agreement always printed `fix: also write ...`,
    also for CentralEmployee.orgUnitId and Employee.sapReference, which `check --static --all` reports no break for, and
    listed Project.leaderId's eight production writes with no mark, though two of them (migration.service.ts
    importProjects, project.service.ts create) are the block's breakers. The view now marks each write the block's
    pair finding names (`missing PARTNER: ...`, the same reading), prints the fix line only then, with the
    agreement's on= limit, and does not list a marked write again; a create an on=update agreement does not hold
    stays an ordinary write."""
    _commit(tmp_path, {
        'backend/prisma/schema.prisma': PT_PAIRS_SCHEMA,
        'backend/src/services/project-member.service.ts': """export const projectMemberService = {
  // flowguard: together Project.leaderId ProjectMember.*
  async assignProjectManager(prisma: any, projectId: string, employeeId: string) {
    return prisma.$transaction(async (tx: any) => {
      await tx.projectMember.create({ data: { id: 'm', projectId, employeeId, role: 'PROJECT_MANAGER' } });
      await tx.project.update({ where: { id: projectId }, data: { leaderId: employeeId } });
    });
  },
};
""",
        'backend/src/services/project.service.ts': """export const projectService = {
  async create(prisma: any, input: any) {
    return prisma.$transaction(async (tx: any) => {
      const created = await tx.project.create({
        data: { id: input.id, leaderId: input.leaderId },
      });
      return created;
    });
  },
};
""",
        'backend/src/services/migration.service.ts': """export async function importProjects(prisma: any, rows: any[]) {
  for (const row of rows) {
    await prisma.project.create({ data: { id: row.id, leaderId: row.leaderId } });
  }
}
""",
        'backend/tests/integration/project.routes.test.ts': """export async function ensureFixtures(prisma: any) {
  await prisma.project.create({ data: { id: 'p1', leaderId: 'e1' } });
}
""",
        'backend/src/services/sap-number-renumber.service.ts': """// flowguard: together Employee.sapReference Opportunity.responsibleSapNumber on=update
export async function renumberSapNumber(prisma: any, id: string, oldNumber: number, newNumber: number) {
  await prisma.employee.update({ where: { id }, data: { sapReference: newNumber } });
  await prisma.opportunity.updateMany({ where: { responsibleSapNumber: oldNumber }, data: { responsibleSapNumber: newNumber } });
}
""",
        'backend/src/services/employee.service.ts': """export const employeeService = {
  async create(prisma: any, input: any) {
    return prisma.employee.create({ data: { id: input.id, sapReference: input.sapReference } });
  },
  async correctSapReference(prisma: any, id: string, sapReference: number) {
    return prisma.employee.update({ where: { id }, data: { sapReference } });
  },
};
""",
    })
    code, text = _flowguard(tmp_path, 'show', 'Project.leaderId')
    lines = text.splitlines()
    assert code == 0 and lines[0] == 'show Project.leaderId' and lines[1].startswith('Map: '), text
    start = lines.index('together Project.leaderId ProjectMember.* backend/src/services/project-member.service.ts:2')
    assert lines[start + 1:start + 4] == [
        'missing ProjectMember.*: backend/src/services/migration.service.ts:3 importProjects (create)',
        'missing ProjectMember.*: backend/src/services/project.service.ts:5 create (create)',
        'fix: also write ProjectMember.* in the same operation as each write marked missing; an '
        'except=path:function(reason) on the together agreement (backend/src/services/project-member.service.ts:2) '
        "loosens it, which is the owner's decision and the next run shows as loosened"], text
    # the marked writes are not listed again; the held write and the test's fixture are ordinary writes
    assert [line for line in lines if line.startswith('writes ')] == [
        'writes Project.leaderId backend/src/services/project-member.service.ts:6 assignProjectManager (update)',
        'writes Project.leaderId backend/tests/integration/project.routes.test.ts:2 ensureFixtures (create)'], text
    # the block's pair findings name the same writes
    code, text = _flowguard(tmp_path, 'check', '--static', '--all')
    assert code == 0 and [line.partition(' was ')[0] for line in text.splitlines() if ' together ' in line] == [
        'before: together Project.leaderId at migration.service.ts:importProjects',
        'before: together Project.leaderId at project.service.ts:create',
        'before: together Employee.sapReference at employee.service.ts:correctSapReference'], text
    # on=update: the update that misses the partner is marked, with the limit in the fix; the create is not held
    code, text = _flowguard(tmp_path, 'show', 'Employee.sapReference')
    lines = text.splitlines()
    assert code == 0 and [line for line in lines if line.startswith(('missing ', 'fix: '))] == [
        'missing Opportunity.responsibleSapNumber: backend/src/services/employee.service.ts:6 correctSapReference (update)',
        'fix: also write Opportunity.responsibleSapNumber in the same operation as each write marked missing (the agreement '
        'holds updates only); an except=path:function(reason) on the together agreement '
        "(backend/src/services/sap-number-renumber.service.ts:1) loosens it, which is the owner's decision and the next run "
        'shows as loosened'], text
    assert [line for line in lines if line.startswith('writes ')] == [
        'writes Employee.sapReference backend/src/services/employee.service.ts:3 create (create)',
        'writes Employee.sapReference backend/src/services/sap-number-renumber.service.ts:3 renumberSapNumber (update)'], text


def test_show_of_a_prisma_enum_name_lists_its_members_from_every_schema(tmp_path):
    """Planning Tool (5.0 review, pt:F11): `show AssignmentStatus` and `show CentralOrgUnitType` printed word matches
    only (`report.service.ts:isIncludedAssignmentStatus` first), though `show Assignment.status` listed the enum's
    members: those enums exist only in the provider templates schema.sqlite.prisma, and a bare name read only JS/TS
    value sets. A bare enum name now lists the members of each Prisma enum of that name (archived and test files
    left out), worded as the field view's line for a schema not in use, with no suffix for a schema in use; the word
    matches wait for --full."""
    sqlite = """datasource db {
  provider = "sqlite"
  url      = "file:./dev.db"
}

enum AssignmentStatus {
  DRAFT
  ACTIVE
  CLOSED
}

enum AppRole {
  SYSTEM_ADMIN
  EMPLOYEE
}

model Assignment {
  id     String           @id
  status AssignmentStatus @default(DRAFT)
}
"""
    _commit(tmp_path, {
        'backend/prisma/schema.prisma': PT_SCHEMA,
        'backend/prisma/schema.sqlite.prisma': sqlite,
        'backend/prisma/schema.sqlserver.prisma': sqlite.replace('"sqlite"', '"sqlserver"'),
        'backend/prisma/central/schema.prisma': 'datasource db {\n  provider = "sqlserver"\n  url      = env("CENTRAL_DATABASE_URL")\n}\n\n'
                                                'model CentralOrgUnit {\n  id   String @id\n  type String\n}\n',
        'backend/prisma/central/schema.sqlite.prisma': 'datasource db {\n  provider = "sqlite"\n  url      = "file:./central.db"\n}\n\n'
                                                       'enum CentralOrgUnitType {\n  ENTITY\n  BU\n  TEAM\n}\n\n'
                                                       'model CentralOrgUnit {\n  id   String             @id\n  type CentralOrgUnitType\n}\n',
        'jobs/prisma/schema.prisma': 'datasource db {\n  provider = "postgresql"\n  url      = env("JOBS_DATABASE_URL")\n}\n\n'
                                     'enum JobState {\n  QUEUED\n  DONE\n}\n\nmodel Job {\n  id    String   @id\n  state JobState\n}\n',
        'backend/tests/fixtures/prisma/schema.prisma': 'enum FixtureState {\n  A\n  B\n}\n',
        'backend/src/types/prisma-enums.ts': "export type AppRole = 'DEVELOPER' | 'SYSTEM_ADMIN' | 'EMPLOYEE';\n",
        'backend/src/services/report.service.ts': ("export function isIncludedAssignmentStatus(status: string) {\n"
                                                   "  return status !== 'REMOVED';\n}\n"),
    })
    def shown(name, *options):
        code, text = _flowguard(tmp_path, 'show', name, *options)
        assert code == 0, text
        return text.splitlines()
    lines = shown('AssignmentStatus')
    assert lines[2:] == ['values AssignmentStatus: DRAFT | ACTIVE | CLOSED (enum AssignmentStatus '
                         'backend/prisma/schema.sqlite.prisma:6, backend/prisma/schema.sqlserver.prisma:6, schemas not in use)',
                         '... 2 more lines, 1 of them only shares a word with AssignmentStatus: python -m flowguard show '
                         'AssignmentStatus --full lists them all'], lines
    assert 'typescript/backend/src/services/report.service.ts:isIncludedAssignmentStatus backend/src/services/report.service.ts:1' \
        in shown('AssignmentStatus', '--full')
    assert [line for line in shown('CentralOrgUnitType') if line.startswith('values ')] == [
        'values CentralOrgUnitType: ENTITY | BU | TEAM (enum CentralOrgUnitType backend/prisma/central/schema.sqlite.prisma:6, '
        'a schema not in use)']
    assert [line for line in shown('JobState') if line.startswith('values ')] == [
        'values JobState: QUEUED | DONE (enum JobState jobs/prisma/schema.prisma:6)']
    # a TS copy of the enum is listed first, as before; the template's own members beside it
    assert [line for line in shown('AppRole') if line.startswith('values ')] == [
        'values AppRole: DEVELOPER | SYSTEM_ADMIN | EMPLOYEE (backend/src/types/prisma-enums.ts:1)',
        'values AppRole: SYSTEM_ADMIN | EMPLOYEE (enum AppRole backend/prisma/schema.sqlite.prisma:12, '
        'backend/prisma/schema.sqlserver.prisma:12, schemas not in use)']
    assert not [line for line in shown('FixtureState') if line.startswith('values ')]     # only a test folder declares it


def _options(name, labels):
    return (f'const {name}: {{ value: Granularity; label: string }}[] = [\n'
            + ''.join(f"  {{ value: '{key}', label: '{label}' }},\n" for key, label in labels) + '];\n')


GRANULARITIES = [('DAY', 'Day'), ('WEEK', 'Week'), ('MONTH', 'Month'), ('YEAR', 'Year')]


def test_show_of_a_label_table_prints_its_keys_and_the_finding_its_family_has(tmp_path):
    """Planning Tool (5.0 review, pt:F13): the block said `before: labels GRANULARITY_OPTIONS at
    UtilizationToolbar.tsx:GRANULARITY_OPTIONS was broken at task start`, and `show GRANULARITY_OPTIONS` printed only
    functions sharing a word with it (`EmployeeUtilizationView.tsx:translateEditsToNewGranularity`): no table and
    no finding, so nothing said that AbsenceCalendarCard.tsx's GRANULARITY_TO_INTERVAL lacks YEAR. show now lists
    each JS/TS table of that name the labels check reads with its keys and labels, and the structure finding of its
    family (`health.labels`); the word matches wait for --full. Its step (5.0 review, pt-rereview-18, R101) says that
    whether the differences are meant is the owner's decision, as the writers and together steps say who decides, and
    names only the repair the family needs: ROLE_LABELS lacks no key, GRANULARITY_TO_INTERVAL spells no label otherwise."""
    component = 'export function {0}() {{\n  return null;\n}}\n'
    _commit(tmp_path, {
        'frontend/src/components/employee-utilization/UtilizationToolbar.tsx':
            "import type { Granularity } from '../../types';\n\n" + _options('GRANULARITY_OPTIONS', GRANULARITIES)
            + component.format('UtilizationToolbar'),
        'frontend/src/components/shared/PlanningTimeControls.tsx':
            _options('GRANULARITY_OPTIONS', GRANULARITIES) + component.format('PlanningTimeControls'),
        'frontend/src/components/calendars/AbsenceCalendarCard.tsx': (
            "/** Map Granularity to CalendarInterval for the aggregation logic. */\n"
            "const GRANULARITY_TO_INTERVAL: Record<string, CalendarInterval> = {\n  DAY: 'day',\n  WEEK: 'week',\n  MONTH: 'month',\n};\n"
            + component.format('AbsenceCalendarCard')),
        'frontend/src/components/employee-utilization/EmployeeUtilizationView.tsx':
            'function translateEditsToNewGranularity(edits: string[]) {\n  return edits;\n}\nexport { translateEditsToNewGranularity };\n',
        'frontend/src/components/admin/PermissionMatrix.tsx': (
            "/** Human-readable labels for role display. */\nconst ROLE_LABELS: Record<string, string> = {\n"
            "  SYSTEM_ADMIN: 'Sys Admin',\n  TEAM_LEADER: 'Team Lead',\n  MANAGEMENT: 'Mgmt',\n  EMPLOYEE: 'Employee',\n};\n"
            + component.format('PermissionMatrix')),
        'frontend/src/components/admin/ScopeMatrix.tsx': (
            "const ROLE_LABELS: Record<string, string> = {\n"
            "  SYSTEM_ADMIN: 'System Admin',\n  TEAM_LEADER: 'Team Leader',\n  MANAGEMENT: 'Management',\n  EMPLOYEE: 'Employee',\n};\n"
            + component.format('ScopeMatrix')),
        'frontend/tests/unit/roles.test.tsx': "const ROLE_LABELS: Record<string, string> = {\n  A: 'Alpha',\n  B: 'Beta',\n  C: 'Gamma',\n};\n",
    })
    def shown(name, *options):
        code, text = _flowguard(tmp_path, 'show', name, *options)
        assert code == 0, text
        return text.splitlines()
    lines = shown('GRANULARITY_OPTIONS')
    assert lines[2:] == [
        "table GRANULARITY_OPTIONS: DAY 'Day', WEEK 'Week', MONTH 'Month', YEAR 'Year' "
        '(frontend/src/components/employee-utilization/UtilizationToolbar.tsx:3, frontend/src/components/shared/PlanningTimeControls.tsx:1)',
        'structure: Label tables disagree: frontend/src/components/employee-utilization/UtilizationToolbar.tsx:3 GRANULARITY_OPTIONS, '
        'frontend/src/components/shared/PlanningTimeControls.tsx:1 GRANULARITY_OPTIONS, '
        'frontend/src/components/calendars/AbsenceCalendarCard.tsx:2 GRANULARITY_TO_INTERVAL: GRANULARITY_TO_INTERVAL lacks YEAR -> '
        "derive these tables from one source, or add the missing keys; whether the differences are meant (abbreviations or "
        "another purpose) is the owner's decision; if they are, after python -m flowguard check --static --all, python -m "
        'flowguard known add labels:frontend/src/components/employee-utilization/UtilizationToolbar.tsx:GRANULARITY_OPTIONS '
        '--act leave --why TEXT records that',
        '... 2 more lines, 1 of them only shares a word with GRANULARITY_OPTIONS: python -m flowguard show '
        'GRANULARITY_OPTIONS --full lists them all'], lines
    assert any(line.endswith('translateEditsToNewGranularity frontend/src/components/employee-utilization/EmployeeUtilizationView.tsx:1')
               for line in shown('GRANULARITY_OPTIONS', '--full'))
    # the lookup table that lacks a key gets its family's finding too; a test's table of that name is left out
    assert [line.partition(':')[0] for line in shown('GRANULARITY_TO_INTERVAL') if line.startswith(('table ', 'structure: '))] == [
        'table GRANULARITY_TO_INTERVAL', 'structure']
    assert [line for line in shown('ROLE_LABELS') if line.startswith(('table ', 'structure: '))] == [
        "table ROLE_LABELS: SYSTEM_ADMIN 'Sys Admin', TEAM_LEADER 'Team Lead', MANAGEMENT 'Mgmt', EMPLOYEE 'Employee' "
        '(frontend/src/components/admin/PermissionMatrix.tsx:2)',
        "table ROLE_LABELS: SYSTEM_ADMIN 'System Admin', TEAM_LEADER 'Team Leader', MANAGEMENT 'Management', EMPLOYEE 'Employee' "
        '(frontend/src/components/admin/ScopeMatrix.tsx:1)',
        'structure: Label tables disagree: frontend/src/components/admin/PermissionMatrix.tsx:2 ROLE_LABELS, '
        "frontend/src/components/admin/ScopeMatrix.tsx:1 ROLE_LABELS: MANAGEMENT 'Management' (ROLE_LABELS (ScopeMatrix.tsx:1)) versus "
        "'Mgmt' (ROLE_LABELS (PermissionMatrix.tsx:2)); SYSTEM_ADMIN 'Sys Admin' (ROLE_LABELS (PermissionMatrix.tsx:2)) versus "
        "'System Admin' (ROLE_LABELS (ScopeMatrix.tsx:1)); TEAM_LEADER 'Team Lead' (ROLE_LABELS (PermissionMatrix.tsx:2)) versus "
        "'Team Leader' (ROLE_LABELS (ScopeMatrix.tsx:1)) -> derive these tables from one source, or align their labels; whether "
        "the differences are meant (abbreviations or another purpose) is the owner's decision; if they are, after python -m "
        'flowguard check --static --all, python -m flowguard known add labels:frontend/src/components/admin/PermissionMatrix.tsx:'
        'ROLE_LABELS --act leave --why TEXT records that']
    # pt-smoke-5: after an ordinary run, which reports no old finding (R99), `known add` alone failed with `the last run
    # reported no labels:...`; the step's two commands, in order, record it.
    assert _flowguard(tmp_path, 'check', '--static')[0] == 0
    step = shown('ROLE_LABELS')[-1].partition(' if they are, after ')[2].removesuffix(' records that')
    run, _, record = step.partition(', ')
    assert run == 'python -m flowguard check --static --all' and record.startswith('python -m flowguard known add '), step
    code, text = _flowguard(tmp_path, *run.split()[3:])
    assert code == 0 and [line.partition(' was ')[0] for line in text.splitlines() if ' labels ' in line] == [
        'before: labels ROLE_LABELS at PermissionMatrix.tsx:ROLE_LABELS',
        'before: labels GRANULARITY_OPTIONS at UtilizationToolbar.tsx:GRANULARITY_OPTIONS'], text
    code, text = _flowguard(tmp_path, *record.replace('TEXT', 'abbreviations-for-the-matrix').split()[3:])
    assert code == 0 and 'labels:frontend/src/components/admin/PermissionMatrix.tsx:ROLE_LABELS' in (
        tmp_path / '.flowguard/known.toml').read_text(encoding='utf-8'), text



PT_CHART_CARD = (
    "import type { Granularity } from '../../types';\n\n"
    "const ALL_GRANULARITY_OPTIONS: { value: Granularity; label: string }[] = [\n"
    "  { value: 'DAY', label: 'Day' },\n  { value: 'WEEK', label: 'Week' },\n  { value: 'MONTH', label: 'Month' },\n"
    "  { value: 'YEAR', label: 'Year' },\n];\n\n"
    "const HEADER_SCALE_LABELS: Record<string, string> = {\n  days: 'Days',\n  weeks: 'Weeks',\n  months: 'Mths',\n};\n\n"
    "function getIsoWeeksInYear(year: number): number {\n  const dec28 = new Date(Date.UTC(year, 11, 28));\n"
    "  return Math.ceil(dec28.getUTCDate() / 7);\n}\n\n"
    "export function ChartControlCard() {\n  return getIsoWeeksInYear(2026) + ALL_GRANULARITY_OPTIONS.length"
    " + Object.keys(HEADER_SCALE_LABELS).length;\n}\n")


def test_an_old_label_disagreement_is_a_lead_only_when_the_change_edits_a_table_of_its_family(tmp_path):
    """Planning Tool (5.0 review, pt-rereview-0, R99): an edit of ChartControlCard.tsx inside getIsoWeeksInYear
    (`Date.UTC(year, 11, 28)` to `Date.UTC(year, 11, 28, 0)`), no table edited, printed `before: labels
    GRANULARITY_OPTIONS at UtilizationToolbar.tsx:GRANULARITY_OPTIONS was broken at task start` and `before: labels
    HEADER_SCALE_LABELS ...`: the labels finding counted every edit of a file holding one of its tables. A family's old
    disagreement is a lead only when the change edits the declaration of one of its tables; changing a label stays new."""
    card, toolbar, calendar, header = ('frontend/src/components/shared/ChartControlCard.tsx',
                                       'frontend/src/components/employee-utilization/UtilizationToolbar.tsx',
                                       'frontend/src/components/calendars/AbsenceCalendarCard.tsx',
                                       'frontend/src/components/shared/TimelineHeader.tsx')
    _commit(tmp_path, {
        card: PT_CHART_CARD,
        toolbar: _options('GRANULARITY_OPTIONS', GRANULARITIES) + 'export function UtilizationToolbar() {\n  return GRANULARITY_OPTIONS;\n}\n',
        'frontend/src/components/shared/PlanningTimeControls.tsx':
            _options('GRANULARITY_OPTIONS', GRANULARITIES) + 'export function PlanningTimeControls() {\n  return GRANULARITY_OPTIONS;\n}\n',
        calendar: ("const GRANULARITY_TO_INTERVAL: Record<string, string> = {\n  DAY: 'day',\n  WEEK: 'week',\n  MONTH: 'month',\n};\n"
                   'export function AbsenceCalendarCard() {\n  return GRANULARITY_TO_INTERVAL;\n}\n'),
        header: ("const HEADER_SCALE_LABELS: Record<string, string> = {\n  days: 'Days',\n  weeks: 'Weeks',\n  months: 'Months',\n};\n"
                 'export function TimelineHeader() {\n  return HEADER_SCALE_LABELS;\n}\n'),
    })
    def labels():
        code, text = _flowguard(tmp_path, 'check', '--static')
        assert code == 0, text
        code, last = _flowguard(tmp_path, 'show', '--last')
        return sorted(line.partition(' was ')[0] for line in last.splitlines() if ' labels ' in line)
    code, text = _flowguard(tmp_path, 'check', '--static', '--all')
    assert sorted(line.partition(' was ')[0] for line in text.splitlines() if ' labels ' in line) == [
        'before: labels GRANULARITY_OPTIONS at UtilizationToolbar.tsx:GRANULARITY_OPTIONS',
        'before: labels HEADER_SCALE_LABELS at ChartControlCard.tsx:HEADER_SCALE_LABELS'], text
    _write(tmp_path, {card: PT_CHART_CARD.replace('Date.UTC(year, 11, 28)', 'Date.UTC(year, 11, 28, 0)')})
    assert labels() == []
    # A comment inside a table's declaration, or its members in another order, edits that table: its family's old
    # finding is a lead, the other's not.
    _write(tmp_path, {card: PT_CHART_CARD.replace("  months: 'Mths',\n", "  months: 'Mths', // the header's scale\n")})
    assert labels() == [f'before: labels HEADER_SCALE_LABELS at {card}:HEADER_SCALE_LABELS']
    _write(tmp_path, {card: PT_CHART_CARD.replace("  { value: 'YEAR', label: 'Year' },\n", "  { label: 'Year', value: 'YEAR' },\n")})
    assert labels() == [f'before: labels GRANULARITY_OPTIONS at {toolbar}:GRANULARITY_OPTIONS']

PT_SQL_SCHEMA = """datasource db {
  provider = "sqlserver"
  url      = env("DATABASE_URL")
}

enum AppRole {
  ADMIN
  PLANNER
  VIEWER
}

enum DeputyRole {
  DEPUTY
  LEAD
}

model Assignment {
  id       String  @id
  fteShare Decimal @map("fte_share")
  @@map("assignments")
}

model UserRole {
  id   String  @id
  role AppRole
  note String?
  @@map("user_roles")
}

model DeputyAssignment {
  id   String     @id
  role DeputyRole
  @@map("deputy_assignments")
}
"""
PT_SQL_SETUP = """CREATE TABLE [dbo].[user_roles] (
    [id] NVARCHAR(36) NOT NULL,
    [role] NVARCHAR(20) NOT NULL,
    CONSTRAINT [CK_user_roles_role] CHECK ([role] IN ('ADMIN', 'PLANNER'))
);
GO

CREATE TABLE [dbo].[deputy_assignments] (
    [id] NVARCHAR(36) NOT NULL,
    [role] NVARCHAR(20) NOT NULL,
    CONSTRAINT [CK_deputy_assignments_role] CHECK ([role] IN ('DEPUTY'))
);
GO

CREATE TABLE [dbo].[assignments] (
    [id] NVARCHAR(36) NOT NULL,
    [fte_share] DECIMAL(6,4) NOT NULL,
    CONSTRAINT [CK_assignments_fte_share] CHECK ([fte_share] >= 0.0000 AND [fte_share] <= 2.0000)
);
GO

ALTER TABLE [dbo].[assignments] ADD CONSTRAINT [CK_assignments_id] CHECK ([id] <> '');
GO
"""


def test_an_old_problem_of_a_sql_description_is_a_lead_only_when_the_change_edits_that_tables_statements(tmp_path):
    """Planning Tool (5.0 gate, gate-7, R99): a one-line edit of the assignments CHECK in azure-sql-setup.sql, the edit
    known.fte-share-range leads to, printed 7 `before` lines: the declarations of CapacityCalendarEntry.entryType,
    DeputyAssignment.role, UserRole.role and four more tables of that file, and its file-level columns finding, though
    the change touched none of those tables. A declarations or columns finding of a SQL description is touched only
    when the change edits a statement of its table there (its CREATE TABLE, ALTER TABLE or a CHECK in them, a comment
    inside too), as the labels fix did for label tables; `check --static --all` still lists every one."""
    setup, schema = 'backend/prisma/azure-sql-setup.sql', 'backend/prisma/schema.prisma'
    _commit(tmp_path, {schema: PT_SQL_SCHEMA, setup: PT_SQL_SETUP})

    def leads(*options):
        code, text = _flowguard(tmp_path, 'check', '--static', *options)
        assert code == 0, text
        if not options:
            text = _flowguard(tmp_path, 'show', '--last')[1]
        return sorted(line.partition(' was ')[0].replace(setup, 'azure-sql-setup.sql')
                      for line in text.splitlines() if line.startswith('before: '))
    every = [f'before: columns azure-sql-setup.sql against {schema} at azure-sql-setup.sql',
             'before: declarations DeputyAssignment.role at azure-sql-setup.sql:11',
             'before: declarations UserRole.role at azure-sql-setup.sql:4']
    assert leads('--all') == every
    for old, new in (('[fte_share] <= 2.0000', '[fte_share] <= 1.0000'), ('DECIMAL(6,4)', 'DECIMAL(7,4)'),
                     ("CHECK ([id] <> '')", "CHECK ([id] <> '-')")):
        _write(tmp_path, {setup: PT_SQL_SETUP.replace(old, new)})
        assert leads() == [], new
    # An edit of the user_roles statement, a comment inside it too, touches that table's findings only.
    _write(tmp_path, {setup: PT_SQL_SETUP.replace("[role] NVARCHAR(20) NOT NULL,\n    CONSTRAINT [CK_user_roles",
                                                  "[role] NVARCHAR(20) NOT NULL, -- the app role\n    CONSTRAINT [CK_user_roles")})
    assert leads() == [every[0], every[2]]
    # An edit of the Prisma schema touches the findings as before.
    _write(tmp_path, {setup: PT_SQL_SETUP, schema: PT_SQL_SCHEMA.replace('  VIEWER\n', '  VIEWER\n  // read only\n')})
    assert leads() == every


def test_show_of_a_ts_function_or_anchor_says_once_that_the_map_reads_no_decision_sites_there(tmp_path):
    """Planning Tool (5.0 review, pt:F12): `show typescript/backend/src/services/employee.service.ts:update` printed
    `not searched: not searched: no readable decision sites -> bind the real decision function -> bind the real decision
    site`, and `show ISO_WEEKS_IN_YEAR`, whose three copies are bound, ended with `rules: ` and `copy search unavailable:
    not searched: ... -> bind the real decision function`. The map reads decision sites only in Python code, so
    binding changes nothing there: each view now prints the search's reason once, a TS or TSX function without a
    bind step, and the ANCHOR view no `rules: ` line when no rule names the anchor. A Python function without
    decision sites keeps its one step."""
    week = ('// flowguard: same ISO_WEEKS_IN_YEAR\n{export}function {name}(year: number): number {{\n'
            '  const day = new Date(Date.UTC(year, 11, {day}));\n  return Math.ceil(day.getUTCDate() / 7);\n}}\n')
    _commit(tmp_path, {
        'backend/src/utils/calendar-iso.ts': week.format(export='export ', name='getIsoWeekCountInYear', day=31),
        'frontend/src/components/shared/ChartControlCard.tsx': week.format(export='', name='getIsoWeeksInYear', day=28)
                                                               + 'export function ChartControlCard() {\n  return getIsoWeeksInYear(2026);\n}\n',
        'backend/src/services/employee.service.ts': """export const employeeService = {
  async update(prisma: any, id: string, input: any) {
    return prisma.employee.update({ where: { id }, data: input });
  },
};
""",
        'app/policy.py': 'def describe(value):\n    return str(value)\n',
    })
    code, text = _flowguard(tmp_path, 'show', 'typescript/backend/src/services/employee.service.ts:update')
    assert code == 0 and text.splitlines()[-1] == 'copies not searched: the map reads no decision sites in typescript code', text
    assert text.count('not searched') == 1 and 'bind' not in text, text
    code, text = _flowguard(tmp_path, 'show', 'ISO_WEEKS_IN_YEAR')
    lines = text.splitlines()
    # (gate-6) an agreement's view begins as every view does, says nothing of a model, and names the languages whose
    # decision sites the map does not read in one line
    assert code == 0 and lines[0] == 'show ISO_WEEKS_IN_YEAR' and lines[1].startswith('Map: '), text
    assert lines[-1] == 'copies not searched: the map reads no decision sites in typescript and tsx code', text
    assert text.count('not searched') == 1 and 'not referenced by a current model' not in text, text
    assert not [line for line in lines if line.startswith('rules:')] and 'bind' not in text, text
    code, text = _flowguard(tmp_path, 'show', 'app.policy:describe')
    assert code == 0 and text.count('not searched') == 1 and \
        'copies not searched: no readable decision sites -> bind the real decision function' in text.splitlines(), text


def test_show_lists_only_the_tables_the_labels_check_reads_each_label_as_the_source_spells_it(tmp_path):
    """Planning Tool (5.0 review, H3-0, pt-rereview-10): `show cookieOptions` printed `table cookieOptions: httpOnly True,
    secure None, sameSite 'lax', path '/', maxAge None (backend/src/config/auth.config.ts:24)`, though the source says
    `secure: appConfig.isProduction`, and its word matches then waited for --full; `show appConfig` printed `port None`
    for `parseInt(process.env.PORT ?? '3001', 10)` and `show MVP_CAPABILITY_MAP` `None` for each role array: a table
    line came for every module-level object, its values in Python's spelling. Only the tables the labels check reads
    (at least 3 keys, each a non-empty string) give a table line, each label as the source spells it; another object
    gives none, is still on the map (no `not on the map` line), and its word matches are listed."""
    _commit(tmp_path, {
        'backend/src/config/app.config.ts': """export const appConfig = {
  port: parseInt(process.env.PORT ?? '3001', 10),
  nodeEnv: process.env.NODE_ENV ?? 'development',
  isProduction: process.env.NODE_ENV === 'production',
  jwt: { maxAgeMs: 8 * 60 * 60 * 1000 },
  MONTHLY_BASELINE_HOURS: 160,
};
""",
        'backend/src/config/auth.config.ts': """import { appConfig } from './app.config';

export const cookieOptions = {
  httpOnly: true,
  secure: appConfig.isProduction,
  sameSite: 'lax' as const,
  path: '/',
  maxAge: appConfig.jwt.maxAgeMs,
};
""",
        'backend/src/config/prisma.ts': 'export function buildAppPrismaClient(url: string) {\n  return { url };\n}\n',
        'backend/src/utils/cookies.ts': 'export function writeCookieHeader(name: string) {\n  return name;\n}\n',
        'frontend/src/types/permissions.ts': """export const MVP_CAPABILITY_MAP = {
  viewDashboardPage: ['SYSTEM_ADMIN', 'PLANNING_ADMIN', 'EMPLOYEE'],
  editOwnLeave: ['EMPLOYEE'],
  approveOrConvertProjectRequest: ['SYSTEM_ADMIN'],
} as const;
""",
        'frontend/src/components/projects/ProjectStatusBadge.tsx': (
            'const PROJECT_STATUS_LABELS: Record<string, string> = {\n  ACTIVE: "Active",\n  ON_HOLD: "On hold",\n'
            "  CLOSED: 'Closed',\n  DRAFT: 'Owner\\'s draft',\n};\n"
            'export function ProjectStatusBadge() {\n  return PROJECT_STATUS_LABELS;\n}\n'),
    })
    def shown(name):
        code, text = _flowguard(tmp_path, 'show', name)
        assert code == 0, text
        return text.splitlines()
    for name, match in (('cookieOptions', 'typescript/backend/src/utils/cookies.ts:writeCookieHeader backend/src/utils/cookies.ts:1'),
                        ('appConfig', 'typescript/backend/src/config/prisma.ts:buildAppPrismaClient backend/src/config/prisma.ts:1')):
        lines = shown(name)
        assert not [line for line in lines if line.startswith(('table ', 'not on the map'))], lines
        assert lines[2].startswith('word matches: ') and match in lines, lines
    assert not [line for line in shown('MVP_CAPABILITY_MAP') if line.startswith(('table ', 'not on the map'))]
    assert [line for line in shown('PROJECT_STATUS_LABELS') if line.startswith('table ')] == [
        'table PROJECT_STATUS_LABELS: ACTIVE "Active", ON_HOLD "On hold", CLOSED \'Closed\', DRAFT \'Owner\\\'s draft\' '
        '(frontend/src/components/projects/ProjectStatusBadge.tsx:1)']


def test_show_prints_a_module_object_whose_values_are_all_literals_as_a_const_line(tmp_path):
    """pt-smoke-2 (2026-11): on Planning Tool `show HOURS_PER_PERIOD` said nothing of what it holds, though
    frontend/src/constants/capacity.ts:18 is `export const HOURS_PER_PERIOD: Record<Granularity, number> = { DAY: 8,
    WEEK: 40, MONTH: 160, YEAR: 1920 }` and known.hours-constants is about exactly these values: only the tables the
    labels check reads gave a line. A module-level object whose every value is a literal now prints its value as a const
    line, as the source spells it; one with another value or a member the reader leaves out (a spread) prints nothing,
    and a label table keeps its table line alone."""
    _commit(tmp_path, {
        'frontend/src/constants/capacity.ts': """import type { Granularity } from '../types/employee-utilization.types';

/** Baseline working hours per granularity period (8 h/day, 40 h/week, 160 h/month). */
export const HOURS_PER_PERIOD: Record<Granularity, number> = {
  DAY: 8,
  WEEK: 40,
  MONTH: 160,
  YEAR: 1920,
};

export const DEFAULT_FILTERS = { showInactive: false, unit: null, label: 'All units' };
const BASE_HOURS = { DAY: 8 };
export const EXTENDED_HOURS = { ...BASE_HOURS, WEEK: 40 };
export const PERIOD_HOURS = { DAY: HOURS_PER_PERIOD.DAY, WEEK: 40 };
export const PERIOD_LABELS: Record<Granularity, string> = { DAY: 'Day', WEEK: 'Week', MONTH: 'Month' };
""",
    })
    def shown(name):
        code, text = _flowguard(tmp_path, 'show', name)
        assert code == 0, text
        return [line for line in text.splitlines() if line.startswith(('const ', 'table ', 'not on the map'))]
    assert shown('HOURS_PER_PERIOD') == [
        'const HOURS_PER_PERIOD = { DAY: 8, WEEK: 40, MONTH: 160, YEAR: 1920 } (frontend/src/constants/capacity.ts:4)']
    assert shown('DEFAULT_FILTERS') == [
        "const DEFAULT_FILTERS = { showInactive: false, unit: null, label: 'All units' } (frontend/src/constants/capacity.ts:11)"]
    assert shown('EXTENDED_HOURS') == [] and shown('PERIOD_HOURS') == []
    assert shown('PERIOD_LABELS') == [
        "table PERIOD_LABELS: DAY 'Day', WEEK 'Week', MONTH 'Month' (frontend/src/constants/capacity.ts:15)"]


def test_a_negative_number_is_a_constant_s_literal_and_any_module_constant_is_on_the_map(tmp_path):
    """Z-9 (2026-11): `export const RANGE = { MIN: -1, MAX: 1 }` printed no const line, a negative number not being read
    as a literal, and `export const NEG = -1;` and ``export const TPL = `x`;`` printed `not on the map: no function,
    class, type, constant, ...  is named NEG` (and TPL), which is false. A negative number is a literal in a constant
    and in an all-literal object; a module-level constant whose value the reader does not read is still a name the map
    knows: no `not on the map` line, and no const line either."""
    _commit(tmp_path, {
        'frontend/src/constants/limits.ts': """/** The range a capacity delta may take. */
export const CAPACITY_DELTA_RANGE = { MIN: -1, MAX: 1 } as const;
export const MIN_SAP_REFERENCE = -2_147_483_648;
export const NOT_FOUND_INDEX = -1;
export const API_PREFIX = `/api`;
export const ROUTE_BASE = `${API_PREFIX}/v1`;
export const OFFSET = -NOT_FOUND_INDEX;
""",
    })
    def shown(name):
        code, text = _flowguard(tmp_path, 'show', name)
        assert code == 0, text
        return [line for line in text.splitlines() if line.startswith(('const ', 'table ', 'not on the map'))]
    limits = 'frontend/src/constants/limits.ts'
    assert shown('CAPACITY_DELTA_RANGE') == [f'const CAPACITY_DELTA_RANGE = {{ MIN: -1, MAX: 1 }} ({limits}:2)']
    assert shown('MIN_SAP_REFERENCE') == [f'const MIN_SAP_REFERENCE = -2147483648 ({limits}:3)']
    assert shown('NOT_FOUND_INDEX') == [f'const NOT_FOUND_INDEX = -1 ({limits}:4)']
    for name in ('API_PREFIX', 'ROUTE_BASE', 'OFFSET'):
        assert shown(name) == [], name
    assert shown('NO_SUCH_LIMIT') == ['not on the map: no function, class, type, constant, enum, Prisma model or field, '
                                      'or SQL table or column is named NO_SUCH_LIMIT']


KNOWN_TABLES = """[known.role-abbreviations]
sites   = ["frontend/src/components/admin/PermissionMatrix.tsx:ROLE_LABELS", "frontend/src/components/admin/ScopeMatrix.tsx:ROLE_LABELS"]
why     = "The matrix is narrow, so it abbreviates on purpose"
act     = "leave"
finding = "labels:frontend/src/components/admin/PermissionMatrix.tsx:ROLE_LABELS"

[known.granularity-year]
sites   = ["frontend/src/components/calendars/AbsenceCalendarCard.tsx:GRANULARITY_TO_INTERVAL"]
why     = "The absence calendar has no year view yet"
act     = "fix"
finding = "labels:frontend/src/components/employee-utilization/UtilizationToolbar.tsx:GRANULARITY_OPTIONS"

[known.calendar-writers]
sites   = ["backend/prisma/schema.prisma:CapacityCalendarEntry.value"]
why     = "Each import and grid writes its own entries"
act     = "ask"
asked   = "2026-11-15"
ask     = "Should one service own CapacityCalendarEntry.value?"
finding = "writers:CapacityCalendarEntry.value"
"""


def test_a_structure_line_whose_finding_a_known_entry_names_gives_that_entry_s_step(tmp_path):
    """Planning Tool shape (5.0 review, H3-2): with known.toml's `finding = "labels:...PermissionMatrix.tsx:ROLE_LABELS"`
    (act leave) the block said `known: known.role-abbreviations at PermissionMatrix.tsx:ROLE_LABELS -> left as it is on
    purpose; ...`, while `show ROLE_LABELS` still ended its structure line with `python -m flowguard known add
    labels:... --act leave --why TEXT records that`, the step to record an entry that is recorded. A structure line
    whose finding an entry names now gives that entry's step, as its known line does: two labels families (a leave and
    a fix entry) and a field that several files write (an ask entry)."""
    _commit(tmp_path, {
        '.flowguard/known.toml': KNOWN_TABLES,
        'frontend/src/components/admin/PermissionMatrix.tsx': (
            "const ROLE_LABELS: Record<string, string> = {\n  SYSTEM_ADMIN: 'Sys Admin',\n  TEAM_LEADER: 'Team Lead',\n"
            "  MANAGEMENT: 'Mgmt',\n  EMPLOYEE: 'Employee',\n};\nexport function PermissionMatrix() {\n  return ROLE_LABELS;\n}\n"),
        'frontend/src/components/admin/ScopeMatrix.tsx': (
            "const ROLE_LABELS: Record<string, string> = {\n  SYSTEM_ADMIN: 'System Admin',\n  TEAM_LEADER: 'Team Leader',\n"
            "  MANAGEMENT: 'Management',\n  EMPLOYEE: 'Employee',\n};\nexport function ScopeMatrix() {\n  return ROLE_LABELS;\n}\n"),
        'frontend/src/components/employee-utilization/UtilizationToolbar.tsx':
            _options('GRANULARITY_OPTIONS', GRANULARITIES) + 'export function UtilizationToolbar() {\n  return null;\n}\n',
        'frontend/src/components/shared/PlanningTimeControls.tsx':
            _options('GRANULARITY_OPTIONS', GRANULARITIES) + 'export function PlanningTimeControls() {\n  return null;\n}\n',
        'frontend/src/components/calendars/AbsenceCalendarCard.tsx': (
            "const GRANULARITY_TO_INTERVAL: Record<string, string> = {\n  DAY: 'day',\n  WEEK: 'week',\n  MONTH: 'month',\n};\n"
            'export function AbsenceCalendarCard() {\n  return GRANULARITY_TO_INTERVAL;\n}\n'),
        'backend/prisma/schema.prisma': PT_CAPACITY_MODEL,
        'backend/src/services/capacity.service.ts': """export const capacityService = {
  async updateCalendarEntry(prisma: any, id: string, value: number) {
    return prisma.capacityCalendarEntry.update({ where: { id }, data: { value } });
  },
};
""",
        'backend/src/services/migration.service.ts': """export async function importPersonnelCapacityEntries(prisma: any, value: number) {
  await prisma.capacityCalendarEntry.create({ data: { id: 'c', value } });
}
""",
        'backend/src/services/utilization-grid.service.ts': """export async function batchUpdateUtilization(prisma: any, id: string, value: number) {
  await prisma.capacityCalendarEntry.update({ where: { id }, data: { value } });
}
""",
    })
    def structure(name):
        code, text = _flowguard(tmp_path, 'show', name)
        assert code == 0, text
        return [line for line in text.splitlines() if line.startswith('structure: ')]
    lines = structure('ROLE_LABELS')
    assert len(lines) == 1 and lines[0].startswith('structure: Label tables disagree: ') and lines[0].endswith(
        ' -> known.role-abbreviations: left as it is on purpose; yours to change only if your task is about it'), lines
    assert 'known add' not in lines[0], lines
    assert [line.partition(' -> ')[2] for line in structure('GRANULARITY_TO_INTERVAL')] == [
        'known.granularity-year: marked to fix when its code changes']
    assert structure('CapacityCalendarEntry.value') == [
        'structure: CapacityCalendarEntry.value is written by 3 files in 3 places without a registered writer agreement '
        '(the writes lines below list them) -> known.calendar-writers: asked the owner on 2026-11-15; no answer yet']
    code, text = _flowguard(tmp_path, 'check', '--static', '--all')
    assert code == 0 and 'known: known.role-abbreviations at PermissionMatrix.tsx:ROLE_LABELS -> left as it is on purpose; ' \
        'yours to change only if your task is about it' in text.splitlines(), text


PT_ORG_UNIT_SCHEMA = """datasource db {
  provider = "sqlserver"
  url      = env("DATABASE_URL")
}

model Employee {
  id                   String @id
  organizationalUnitId String @map("organizational_unit_id")
  email                String
  name                 String
  @@map("employees")
}
"""


def test_show_of_a_field_without_writers_counts_its_places_and_lists_its_writes_in_line_order(tmp_path):
    """Planning Tool (5.0 review, pt-rereview-15, pt-rereview-16, H3-3): `show Employee.organizationalUnitId` named its
    22 write places in the structure line and then listed the same 22 as writes lines; each of its five together
    candidates repeated the same `not by ...changeEmployeeHomeUnit ...remove ...removeWithReassignment` tail; and the
    writes were sorted as text, so `employee.service.ts:1315 ... updateAsManager.persist` came before `:641 create`.
    The structure line now counts the places and says the writes below list them, a tail an earlier candidate's line
    names is said once, and the writes come in line order, the unclear write after the others and before the reads."""
    _commit(tmp_path, {
        'backend/prisma/schema.prisma': PT_ORG_UNIT_SCHEMA,
        'backend/src/services/employee.service.ts': """export const employeeService = {
  async create(prisma: any, input: any) {
    return prisma.employee.create({ data: { id: input.id, organizationalUnitId: input.unit, email: input.email, name: input.name } });
  },
  async update(prisma: any, id: string, input: any) {
    return prisma.employee.update({ where: { id }, data: { organizationalUnitId: input.unit, email: input.email, name: input.name } });
  },
  async patch(prisma: any, id: string, input: any) {
    return prisma.employee.update({ where: { id }, data: input });
  },
};
export async function updateAsManager(prisma: any, id: string, input: any) {
  return prisma.employee.update({ where: { id }, data: { organizationalUnitId: input.unit, email: input.email, name: input.name } });
}
""",
        'backend/src/services/employee-home-unit.service.ts': """export async function changeEmployeeHomeUnit(prisma: any, id: string, unit: string) {
  await prisma.employee.updateMany({ where: { id }, data: { organizationalUnitId: unit } });
}
""",
        'backend/src/services/org-unit.service.ts': """export async function removeWithReassignment(prisma: any, from: string, to: string) {
  await prisma.employee.updateMany({ where: { organizationalUnitId: from }, data: { organizationalUnitId: to } });
}
""",
        'backend/src/services/import.service.ts': """export class ImportService {
  async commitEmployees(prisma: any, rows: any[]) {
    for (const row of rows) {
      await prisma.employee.create({ data: { id: row.id, organizationalUnitId: row.unit, email: row.email, name: row.name } });
    }
  }
}
""",
        'backend/src/services/report.service.ts': """export async function listUnitEmployees(prisma: any, unit: string) {
  return prisma.employee.findMany({ where: { organizationalUnitId: unit } });
}
""",
    })
    code, text = _flowguard(tmp_path, 'show', 'Employee.organizationalUnitId', '--full')
    lines = text.splitlines()
    assert code == 0, text
    assert [line.partition(' -> ')[0] for line in lines if line.startswith(('structure: ', 'together candidate'))] == [
        'structure: Employee.organizationalUnitId is written by 4 files in 6 places without a registered writer agreement '
        '(the writes lines below list them)',
        'together candidate (reference only): Employee.email is written by 4 of the 6 functions that write '
        'Employee.organizationalUnitId; not by backend/src/services/employee-home-unit.service.ts:2 changeEmployeeHomeUnit  '
        'backend/src/services/org-unit.service.ts:2 removeWithReassignment',
        'together candidate (reference only): Employee.name is written by 4 of the 6 functions that write '
        'Employee.organizationalUnitId; not by the 2 functions named for Employee.email'], text
    assert [line for line in lines if line.startswith(('writes ', 'reads '))] == [
        'writes Employee.organizationalUnitId backend/src/services/employee-home-unit.service.ts:2 changeEmployeeHomeUnit (updateMany)',
        'writes Employee.organizationalUnitId backend/src/services/employee.service.ts:3 create (create)',
        'writes Employee.organizationalUnitId backend/src/services/employee.service.ts:6 update (update)',
        'writes Employee.organizationalUnitId backend/src/services/employee.service.ts:13 updateAsManager (update)',
        'writes Employee.organizationalUnitId backend/src/services/import.service.ts:4 ImportService.commitEmployees (create)',
        'writes Employee.organizationalUnitId backend/src/services/org-unit.service.ts:2 removeWithReassignment (updateMany)',
        'writes Employee.? backend/src/services/employee.service.ts:9 patch (update; unclear: input is a parameter)',
        'reads Employee backend/src/services/report.service.ts:2 listUnitEmployees (findMany)'], text


def test_the_anchor_view_of_an_agreement_names_its_place_its_writers_as_written_and_each_write_once(tmp_path):
    """Planning Tool (5.0 review, pt-rereview-11 to 14, H3-4): the ANCHOR view of Project.lifecycleStatusId began with
    `anchor Project.lifecycleStatusId -> typescript/backend/src/services/project.service.ts: backend/src/services/
    project.service.ts:32` (the map's module id, an empty symbol), listed the one assignment `updateData.lifecycleStatusId
    = lifecycleStatusId;` of ImportService.commitProjects twice (`(update)` and `...commitProjects.<anonymous@1506,33>
    (assign)`), said `fix: call create or update instead` of the agreement's `projectService.create,projectService.update`,
    and ended with `historical observations`, `owner; no inputs; {}`, `results: {}; 0 distinct observed outputs` and `info:
    not referenced by a current model`, which hold nothing for an agreement no test observed. The anchor line now gives the
    agreement's place, each write place is listed once (in the block too), the fix and the block's step name the writers as
    the agreement spells them, and the empty observation lines and the model line are gone; a `same` copy keeps its
    model line. A bound Python anchor without decision sites is told no binding step."""
    _commit(tmp_path, {
        'backend/prisma/schema.prisma': PT_PAIRS_SCHEMA.replace(
            '  leaderId String          @map("leader_id")\n',
            '  leaderId String          @map("leader_id")\n  lifecycleStatusId String @map("lifecycle_status_id")\n'),
        'backend/src/services/project.service.ts': """// flowguard: writers Project.lifecycleStatusId projectService.create,projectService.update
export const projectService = {
  async create(prisma: any, input: any) {
    return prisma.project.create({ data: { id: input.id, leaderId: input.leaderId, lifecycleStatusId: input.statusId } });
  },
  async update(prisma: any, id: string, input: any) {
    return prisma.project.update({ where: { id }, data: { lifecycleStatusId: input.statusId } });
  },
};
""",
        'backend/src/services/import.service.ts': """export class ImportService {
  async commitProjects(prisma: any, projects: any[], lifecycleStatusId: string) {
    await prisma.$transaction(async (tx: any) => {
      for (const proj of projects) {
        const updateData: Record<string, unknown> = {};
        if (proj.overwrite) {
          updateData.lifecycleStatusId = lifecycleStatusId;
        }
        if (Object.keys(updateData).length > 0) {
          await tx.project.update({
            where: { id: proj.matchedProjectId },
            data: updateData,
          });
        }
      }
    });
  }
}
""",
        'backend/src/services/sap-number-renumber.service.ts': """// flowguard: together Employee.sapReference Opportunity.responsibleSapNumber on=update
export async function renumberSapNumber(prisma: any, id: string, oldNumber: number, newNumber: number) {
  await prisma.employee.update({ where: { id }, data: { sapReference: newNumber } });
  await prisma.opportunity.updateMany({ where: { responsibleSapNumber: oldNumber }, data: { responsibleSapNumber: newNumber } });
}
""",
        'app/rates.py': '# flowguard: same LATE_FEE\ndef late_fee(days):\n    return days * 2\n',
        'app/billing.py': '# flowguard: same LATE_FEE\ndef overdue_fee(days):\n    return days * 2\n',
    })
    empty = ('historical observations', 'distinct observed outputs', 'no inputs', 'not referenced by a current model')
    code, text = _flowguard(tmp_path, 'show', 'Project.lifecycleStatusId')
    lines = text.splitlines()
    assert code == 0 and lines[0] == 'show Project.lifecycleStatusId' and lines[1].startswith('Map: ') and lines[2:4] == [
        'anchor Project.lifecycleStatusId -> backend/src/services/project.service.ts:1',
        'writers Project.lifecycleStatusId projectService.create,projectService.update backend/src/services/project.service.ts:1'], text
    assert [line for line in lines if line.startswith(('outside writers: ', 'fix: '))] == [
        'outside writers: backend/src/services/import.service.ts:7 ImportService.commitProjects (update)',
        'fix: call projectService.create or projectService.update instead; adding a function to the writers agreement '
        "(backend/src/services/project.service.ts:1) loosens it, which is the owner's decision"], text
    assert '<anonymous' not in text and not [line for line in lines if any(part in line for part in empty)], text
    code, text = _flowguard(tmp_path, 'show', 'Employee.sapReference')
    lines = text.splitlines()
    assert code == 0 and lines[2] == 'anchor Employee.sapReference -> backend/src/services/sap-number-renumber.service.ts:1', text
    assert not [line for line in lines if any(part in line for part in empty)], text
    code, text = _flowguard(tmp_path, 'check', '--static', '--all')
    assert code == 0 and [line.partition(' was ')[0] for line in text.splitlines() if ' writers ' in line] == [
        'before: writers Project.lifecycleStatusId at import.service.ts:ImportService.commitProjects'], text
    # a new write outside the writers: the block's step names them as the agreement does
    _write(tmp_path, {'backend/src/services/proposal.service.ts': """export async function finalizeProposal(prisma: any, id: string) {
  return prisma.project.update({ where: { id }, data: { lifecycleStatusId: 'ACTIVE' } });
}
"""})
    code, text = _flowguard(tmp_path, 'check', '--static')
    assert 'red: writers Project.lifecycleStatusId: proposal.service.ts:finalizeProposal writes Project.lifecycleStatusId outside ' \
        'projectService.create, projectService.update -> call projectService.create or projectService.update instead' \
        in text.splitlines(), text
    # a bound Python anchor without decision sites: no binding step, in its ANCHOR view and in its function's view
    code, text = _flowguard(tmp_path, 'show', 'LATE_FEE')
    lines = text.splitlines()
    assert code == 0 and lines[-1] == 'copies not searched: no readable decision sites', text
    assert 'not referenced by a current model' not in text, text
    assert 'historical observations' not in text and 'bind' not in text, text
    code, text = _flowguard(tmp_path, 'show', 'app.rates:late_fee')
    assert code == 0 and 'copies not searched: no readable decision sites' in text.splitlines() and 'bind' not in text, text


# Planning Tool's capacity code (2026-11, K3), as backend/src/utils/capacity-conversion.ts, capacity.service.ts,
# employee.service.ts and their routes spell it: an exported function its own file calls, object-literal services whose
# methods a route calls as `capacityService.updateCalendarEntry(...)` (a call matched by the holder's name, not
# resolved), a method that writes through a nested `persist`, a test file of callbacks, and the three Prisma schemas,
# the SQL setup script and the migrations folder that declare the model and its table.
PT_CAPACITY_MODEL = """model CapacityCalendarEntry {
  id         String   @id @default(uuid())
  employeeId String   @map("employee_id")
  startDate  DateTime @map("start_date")
  value      Decimal  @db.Decimal(10, 4)
  unitType   String   @map("unit_type")
  employee   Employee @relation(fields: [employeeId], references: [id])
  @@map("capacity_calendar_entries")
}

model Employee {
  id                   String  @id
  name                 String
  organizationalUnitId String? @map("organizational_unit_id")
  fteShare             Decimal @map("fte_share")
  entries              CapacityCalendarEntry[]
  @@map("employees")
}

model CentralEmployee {
  id    String @id
  name  String
  email String
  @@map("central_employees")
}

model Assignment {
  id       String  @id
  fteShare Decimal @map("fte_share")
  @@map("assignments")
}

model AbsencePhase {
  id       String  @id
  fteShare Decimal @map("fte_share")
  @@map("absence_phases")
}
"""
PT_CAPACITY_TABLE = """CREATE TABLE capacity_calendar_entries (
  id NVARCHAR(36) NOT NULL PRIMARY KEY,
  employee_id NVARCHAR(36) NOT NULL,
  start_date DATETIME2 NOT NULL,
  value DECIMAL(10,4) NOT NULL,
  unit_type NVARCHAR(20) NOT NULL
);
"""
PT_CAPACITY = {
    'backend/prisma/schema.prisma': 'datasource db {\n  provider = "sqlserver"\n  url      = env("DATABASE_URL")\n}\n\n' + PT_CAPACITY_MODEL,
    'backend/prisma/schema.sqlite.prisma': 'datasource db {\n  provider = "sqlite"\n  url      = "file:./dev.db"\n}\n\n' + PT_CAPACITY_MODEL,
    'backend/prisma/schema.sqlserver.prisma': 'datasource db {\n  provider = "sqlserver"\n  url      = env("DATABASE_URL")\n}\n\n' + PT_CAPACITY_MODEL,
    'backend/prisma/azure-sql-setup.sql': PT_CAPACITY_TABLE,
    'backend/prisma/migrations/20260317073846_init/migration.sql': PT_CAPACITY_TABLE.replace(',\n  unit_type NVARCHAR(20) NOT NULL', ''),
    'backend/prisma/migrations/20260427120000_add_unit_type/migration.sql':
        'ALTER TABLE capacity_calendar_entries ADD unit_type NVARCHAR(20) NOT NULL;\n',
    'backend/src/utils/capacity-conversion.ts': """export const DAILY_BASELINE_HOURS = 8;

export function convertHoursToPercent(hours: number, baselineHours: number): number {
  return (hours / baselineHours) * 100;
}

/** Hours of a percent share of the baseline. */
export function convertPercentToHours(percent: number, baselineHours: number, precision = 4): number {
  return Number(((percent / 100) * baselineHours).toFixed(precision));
}

export function convertCapacityValue(value: number, unit: string): number {
  return unit === 'PERCENT' ? convertPercentToHours(value, DAILY_BASELINE_HOURS) : value;
}
""",
    'backend/src/services/capacity.service.ts': """export const capacityService = {
  async updateCalendarEntry(prisma: any, entryId: string, input: any) {
    const entry = await prisma.capacityCalendarEntry.findUnique({ where: { id: entryId } });
    return prisma.capacityCalendarEntry.update({ where: { id: entry.id }, data: { value: input.value, unitType: input.unitType } });
  },
  async listCalendarEntries(prisma: any, employeeId: string) {
    return prisma.capacityCalendarEntry.findMany({ where: { employeeId } });
  },
};
""",
    'backend/src/services/employee.service.ts': """export const employeeService = {
  async update(prisma: any, id: string, input: any) {
    const persist = async () => prisma.employee.update({
      where: { id }, data: { name: input.name, organizationalUnitId: input.unitId, fteShare: input.share },
    });
    await persist();
    return prisma.centralEmployee.update({ where: { id }, data: { name: input.name, email: input.email } });
  },
};
""",
    'backend/src/services/central-employee.service.ts': """export const centralEmployeeService = {
  async update(prisma: any, id: string, input: any) {
    return prisma.centralEmployee.update({ where: { id }, data: { email: input.email } });
  },
};
""",
    'backend/src/services/absence.service.ts': 'export async function update(prisma: any, id: string) { return id; }\n',
    'backend/src/services/allocation.service.ts': 'export async function update(prisma: any, id: string) { return id; }\n',
    'backend/src/api/routes/capacity.routes.ts': """import { capacityService } from '../../services/capacity.service';

export async function putCalendarEntry(prisma: any, request: any) {
  return capacityService.updateCalendarEntry(prisma, request.params.id, request.body);
}
""",
    'frontend/src/components/employee-utilization/UtilizationTable.tsx': """export function percentToHours(percent: number): number {
  return percent * 0.4;
}
""",
    'frontend/tests/unit/UtilizationTable.summary-hours.test.tsx': """import { percentToHours } from '../../src/components/employee-utilization/UtilizationTable';

describe('summary hours', () => {
  it('converts a percent to hours', () => {
    expect(percentToHours(50)).toBe(20);
  });
});
""",
    'frontend/src/components/import/ImportResultStep.tsx': """export function CountCard(props: { count: number }) {
  return props.count;
}
export function countLeaves(rows: number[]): number {
  return rows.length;
}
""",
}


def _shown_lines(root, *arguments):
    code, text = _flowguard(root, 'show', *arguments)
    assert code == 0, text
    return text.splitlines()


def test_show_of_an_exact_function_or_object_method_name_prints_its_node_view_before_the_word_matches(tmp_path):
    """Planning Tool (5.0 re-review, pt-rereview-5 and 20): `show convertPercentToHours` printed the function's id among
    35 functions that share a word with it, test callbacks included, and no signature; `show
    capacityService.updateCalendarEntry` 36 such lines and `... 3375 more lines`; the node view said nothing of what a
    function writes or who calls it. A name that names one function, or a few, now prints each one's node view first:
    its id and place, signature and doc, the fields it writes (its nested functions' too) and the functions that call
    it through a call the map resolved, a count and the first three; the names that only share a word wait for --full.
    `show module:qual` prints the same node lines, with no empty line for a missing doc (the map reads no TS doc
    comment)."""
    _commit(tmp_path, PT_CAPACITY)
    conversion = 'backend/src/utils/capacity-conversion.ts'
    lines = _shown_lines(tmp_path, 'convertPercentToHours')
    assert lines[2:5] == [f'typescript/{conversion}:convertPercentToHours {conversion}:8',
                          'function convertPercentToHours(percent: number, baselineHours: number, precision = 4): number ',
                          f'called by 1 function through a resolved call: convertCapacityValue ({conversion}:12)'], lines
    # the functions and test callbacks that share a word follow in --full, after the line that says so; the count is
    # what --full adds
    full = _shown_lines(tmp_path, 'convertPercentToHours', '--full')
    label = full.index('word matches: the 5 lines below only share a word with convertPercentToHours')
    assert full[:label] == lines[:5] and len(full) == label + 6, full
    test = 'tsx/frontend/tests/unit/UtilizationTable.summary-hours.test.tsx'
    assert {line.partition(' ')[0] for line in full[label + 1:]} == {
        f'typescript/{conversion}:convertHoursToPercent', f'typescript/{conversion}:convertCapacityValue',
        'tsx/frontend/src/components/employee-utilization/UtilizationTable.tsx:percentToHours', f'{test}:<anonymous@3,27>',
        f'{test}:<anonymous@3,27>.<anonymous@4,37>'}, full
    assert lines[5:] == ['... 6 more lines, 5 of them only share a word with convertPercentToHours: python -m flowguard '
                         'show convertPercentToHours --full lists them all'], lines
    # object.method: the method of that object, what it writes; a route's `capacityService.updateCalendarEntry(...)`,
    # with `capacityService` imported from the module that defines it, is a resolved call (H4-0)
    service = 'backend/src/services/capacity.service.ts'
    lines = _shown_lines(tmp_path, 'capacityService.updateCalendarEntry')
    assert lines[2:6] == [f'typescript/{service}:updateCalendarEntry {service}:2',
                          'async updateCalendarEntry(prisma: any, entryId: string, input: any) ',
                          'writes 2 fields: CapacityCalendarEntry.unitType, CapacityCalendarEntry.value (python -m '
                          'flowguard show MODEL.FIELD lists the writes and reads of one)',
                          'called by 1 function through a resolved call: putCalendarEntry '
                          '(backend/src/api/routes/capacity.routes.ts:3)'], lines
    # a function no resolved call reaches says so
    assert 'called by no function through a call the map resolved (a call matched by its name alone is not counted)' \
        in _shown_lines(tmp_path, 'countLeaves'), _shown_lines(tmp_path, 'countLeaves')
    assert lines[6].startswith('... ') and 'only share a word with capacityService.updateCalendarEntry' in lines[6], lines
    # the writes of a nested `persist` are the method's; past three fields the line counts them and --full names all
    employee = 'backend/src/services/employee.service.ts'
    lines = _shown_lines(tmp_path, 'employeeService.update')
    assert lines[2:4] == [f'typescript/{employee}:update {employee}:2', 'async update(prisma: any, id: string, input: any) '], lines
    assert lines[4] == ('writes 5 fields: CentralEmployee.email, CentralEmployee.name, Employee.fteShare and 2 more (python -m '
                        f'flowguard show MODEL.FIELD lists the writes and reads of one; python -m flowguard show '
                        f'typescript/{employee}:update --full names them all)'), lines
    assert not [line for line in lines if 'central-employee.service.ts:update ' in line], lines
    node = _shown_lines(tmp_path, f'typescript/{employee}:update', '--full')     # header and Map line first (gate-4)
    assert node[0] == f'show typescript/{employee}:update' and node[1].startswith('Map: ') and '' not in node, node
    assert node[2:5] == [f'typescript/{employee}:update {employee}:2', 'async update(prisma: any, id: string, input: any) ',
                         'writes 5 fields: CentralEmployee.email, CentralEmployee.name, Employee.fteShare, Employee.name, '
                         'Employee.organizationalUnitId (python -m flowguard show MODEL.FIELD lists the writes and reads of one)'], node
    # a generic name that names more functions than the views hold lists them, and its word matches wait too
    lines = _shown_lines(tmp_path, 'update')
    assert lines[2:] == [f'typescript/backend/src/services/{name}.service.ts:update backend/src/services/{name}.service.ts:{line}'
                         for name, line in (('absence', 1), ('allocation', 1), ('central-employee', 2), ('employee', 2))] + [
        '... 3 more lines, 2 of them only share a word with update: python -m flowguard show update --full lists them all'], lines


def test_show_of_a_prisma_model_or_table_name_prints_its_declarations_and_counts_its_writes_and_reads(tmp_path):
    """Planning Tool (5.0 re-review, pt-rereview-6): `show CapacityCalendarEntry` and `show capacity_calendar_entries`
    printed only functions that share a word with them (updateCalendarEntry, normalizeEntryEndDate, an integration
    test's ensureCatalogEntry): no declaration, no @@map table, no write or read, though `show
    CapacityCalendarEntry.valeu` listed the model's reads. A model or table name now prints one line per Prisma schema
    that declares it, with its @@map table and its number of fields, one per SQL description that has the table (a
    migrations folder as its migrations leave it), and a line that counts the writes and reads and names `show
    MODEL.FIELD`; the names that only share a word wait for --full."""
    _commit(tmp_path, PT_CAPACITY)
    models = [f'model CapacityCalendarEntry (table capacity_calendar_entries): 6 fields (backend/prisma/{schema}:6)'
              for schema in ('schema.prisma', 'schema.sqlite.prisma', 'schema.sqlserver.prisma')]
    tables = ['table capacity_calendar_entries: 5 columns (backend/prisma/azure-sql-setup.sql:1)',
              'table capacity_calendar_entries: 5 columns (backend/prisma/migrations/ as its migrations leave it, created at '
              'backend/prisma/migrations/20260317073846_init/migration.sql:1)']
    counts = ('CapacityCalendarEntry on the map: 1 write in 1 function, 2 reads in 2 functions: python -m flowguard show '
              'CapacityCalendarEntry.FIELD lists the writes and reads of one')
    for query in ('CapacityCalendarEntry', 'capacity_calendar_entries'):
        lines = _shown_lines(tmp_path, query)
        assert lines[2:] == [*models, *tables, counts, f'... 7 more lines, 6 of them only share a word with {query}: '
                             f'python -m flowguard show {query} --full lists them all'], lines
        full = _shown_lines(tmp_path, query, '--full')
        assert full[:8] == lines[:8] and full[8] == f'word matches: the 6 lines below only share a word with {query}', full
    # a model without @@map is its own table; a name that is no model or table gets no model line
    lines = _shown_lines(tmp_path, 'Employee')
    assert lines[2:5] == [f'model Employee (table employees): 5 fields (backend/prisma/{schema}:16)'
                          for schema in ('schema.prisma', 'schema.sqlite.prisma', 'schema.sqlserver.prisma')], lines
    assert lines[5] == ('Employee on the map: 1 write in 1 function, 0 reads in 0 functions: python -m flowguard show '
                        'Employee.FIELD lists the writes and reads of one'), lines
    assert not [line for line in _shown_lines(tmp_path, 'convertCapacityValue') if line.startswith(('model ', 'table '))]


GB_SCHEMA = """datasource db {
  provider = "sqlserver"
  url      = env("DATABASE_URL")
}

model Assignment {
  id              String  @id
  fteShare        Decimal @map("fte_share")
  internalOrderId String? @map("internal_order_id") @db.NVarChar(36)
  @@map("assignments")
}

model LendingAssignment {
  id       String  @id
  fteShare Decimal @map("fte_share")
  @@map("lending_assignments")
}

model AbsencePhase {
  id       String  @id
  fteShare Decimal @map("fte_share")
  @@map("absence_phases")
}
"""
# Planning Tool's schema objects as its files spell them (5.0 gate, T10): the assignment schemas of
# employee-utilization.schemas.ts, absencePhaseSchema of personnel-mvp.schemas.ts, PT_ZOD's allocation, batch and
# lending schemas; its init migration and an upgrade script that adds a column to a table the migration creates; a
# service whose module-level constant is a call; a backend package whose scripts run tests/unit and, as a suite that
# reaches real databases, tests/integration, with a vitest config whose test.include takes only `*.test.ts`.
GB_FILES = {
    **PT_ZOD,
    'backend/prisma/schema.prisma': GB_SCHEMA,
    'backend/src/api/schemas/employee-utilization.schemas.ts': """import { z } from 'zod';

const MIN_FTE_SHARE = 0;
const MAX_FTE_SHARE = 2.0;

const assignmentEditSchema = z.object({
  fteShare: z
    .number()
    .min(MIN_FTE_SHARE)
    .max(MAX_FTE_SHARE),
});

export const createAssignmentSchema = z.object({
  employeeId: z.string().uuid(),
  fteShare: z.number().min(MIN_FTE_SHARE).max(MAX_FTE_SHARE),
});
""",
    'backend/src/api/schemas/absence.schemas.ts': """import { z } from 'zod';

const absencePhaseSchema = z
  .object({
    fteShare: z.number().gt(0).lte(1),
  })
  .strict();
""",
    'backend/prisma/migrations/20260317073846_init/migration.sql': """CREATE TABLE "assignments" (
    "id" TEXT NOT NULL,
    "fte_share" DECIMAL NOT NULL,
    CONSTRAINT "assignments_fte_share_check" CHECK ("fte_share" >= 0 AND "fte_share" <= 2)
);
""",
    'backend/prisma/upgrade-internal-orders.sql': 'ALTER TABLE assignments ADD legacy_order_code NVARCHAR(20) NULL;\n',
    'backend/src/services/assignment.service.ts': """export const assignmentCache = new Map<string, number>();

export async function assignBatch(prisma: any, share: number) {
  await prisma.assignment.create({ data: { id: '1', fteShare: share } });
}
""",
    'backend/package.json': '{"name": "backend", "scripts": {"test": "vitest run", "test:unit": "vitest run tests/unit", '
                            '"test:integration": "vitest run tests/integration"}, "devDependencies": {"vitest": "^3.2.4"}}\n',
    'backend/vitest.config.mjs': "import { defineConfig } from 'vitest/config';\n"
                                 "export default defineConfig({ test: { include: ['tests/**/*.test.ts'] } });\n",
    **{f'backend/tests/{name}': "import { assignBatch } from '../../src/services/assignment.service';\n"
                                'export const used = assignBatch;\n'
       for name in ('unit/assignment.service.test.ts', 'integration/assignment.routes.test.ts', 'support/seed-assignments.ts')},
}
ZOD_OTHERS = 'zod lines below are keys of the same name in other schema objects, matched by the name only'


def test_show_of_a_field_lists_the_zod_keys_of_its_own_schema_objects_first_then_those_matched_by_name(tmp_path):
    """Planning Tool (5.0 gate, gate-3): `show LendingAssignment.fteShare` listed the 0..2 keys of the allocation,
    employee-utilization and utilization-grid schemas beside the lending ones, and `show Assignment.fteShare` the lending
    and absence-phase checks, each as if it held for the field. The keys of the schema objects named after the model
    (the name holds the model's name in any letter case) come first; the others follow one line that says they are
    keys of the same name in other schema objects, matched by the name only. Nothing is dropped."""
    _commit(tmp_path, GB_FILES)
    allocation, assignment, personnel, utilization, absence = (
        f'backend/src/api/schemas/{name}.schemas.ts'
        for name in ('allocation', 'assignment', 'personnel-mvp', 'employee-utilization', 'absence'))
    edit = f'zod key fteShare in assignmentEditSchema: MIN_FTE_SHARE=0 <= fteShare <= MAX_FTE_SHARE=2.0 ({utilization}:7)'
    create = f'zod key fteShare in createAssignmentSchema: MIN_FTE_SHARE=0 <= fteShare <= MAX_FTE_SHARE=2.0 ({utilization}:15)'
    phase = f'zod key fteShare in absencePhaseSchema: 0 < fteShare <= 1 ({absence}:5)'
    allocations = [f'zod key fteShare in allocationPeriodSchema: 0 <= fteShare <= 2 ({allocation}:8)',
                   f'zod key fteShare in allocationCreateSchema: 0 <= fteShare <= 2, and a refine that is not read may '
                   f'reject more ({allocation}:13)']
    batch = f'zod key fteShare in batchAssignSchema: 0 <= fteShare <= 1 ({assignment}:11)'
    lending = [f'zod key fteShare in lendingUpdateSchema: 0 < fteShare <= 1, and a refine that is not read may reject more '
               f'({personnel}:9)',
               f'zod key fteShare in capacityEntryCreateSchema: 0 <= fteShare <= MAX_FTE_SHARE=2.0 ({personnel}:18)',
               f'zod key fteShare in phases: 0 < fteShare <= 1 ({personnel}:22, {personnel}:23)']

    def zod(query):
        code, text = _flowguard(tmp_path, 'show', query, '--full')
        assert code == 0 and 'not on the map' not in text, text
        return [line for line in text.splitlines() if line.startswith('zod ') or line.endswith(ZOD_OTHERS)]
    assert zod('Assignment.fteShare') == [edit, create, f'the 7 {ZOD_OTHERS}', phase, *allocations, batch, *lending]
    assert zod('AbsencePhase.fteShare') == [phase, f'the 8 {ZOD_OTHERS}', *allocations, batch, edit, create, *lending]
    # no schema object is named after LendingAssignment (lendingUpdateSchema is not): every key follows the line
    assert zod('LendingAssignment.fteShare') == [f'the 9 {ZOD_OTHERS}', phase, *allocations, batch, edit, create, *lending]


def test_a_zod_schema_object_belongs_to_the_longest_model_name_its_words_hold(tmp_path):
    """5.0 gate (GB-2): a schema object counted as a model's own when its lower-cased name held the model's name, so
    Planning Tool's five Prisma models whose names end in Assignment would all give their schemas to Assignment: a
    `lendingAssignmentCreateSchema` put a lending check back among `show Assignment.fteShare`'s own lines. A schema
    object belongs to the model whose name is the longest model name its camel-case words hold as consecutive
    words (LendingAssignment, not Assignment); only those are the field's own. `batchAssignSchema` holds the word
    assign, not assignment: it belongs to no model."""
    lending = 'backend/src/api/schemas/lending-assignment.schemas.ts'
    _commit(tmp_path, {**GB_FILES, lending: """import { z } from 'zod';

export const lendingAssignmentCreateSchema = z.object({
  fteShare: z.number().gt(0).lte(1),
});
"""})
    utilization = 'backend/src/api/schemas/employee-utilization.schemas.ts'
    own = f'zod key fteShare in lendingAssignmentCreateSchema: 0 < fteShare <= 1 ({lending}:4)'

    def zod(query):
        code, text = _flowguard(tmp_path, 'show', query, '--full')
        assert code == 0 and 'not on the map' not in text, text
        return [line for line in text.splitlines() if line.startswith('zod ') or line.endswith(ZOD_OTHERS)]
    lines = zod('Assignment.fteShare')
    assert lines[:3] == [
        f'zod key fteShare in assignmentEditSchema: MIN_FTE_SHARE=0 <= fteShare <= MAX_FTE_SHARE=2.0 ({utilization}:7)',
        f'zod key fteShare in createAssignmentSchema: MIN_FTE_SHARE=0 <= fteShare <= MAX_FTE_SHARE=2.0 ({utilization}:15)',
        f'the 8 {ZOD_OTHERS}'], lines
    assert own in lines[3:], lines
    lines = zod('LendingAssignment.fteShare')
    assert lines[:2] == [own, f'the 9 {ZOD_OTHERS}'], lines


def test_show_of_a_module_constant_whose_value_is_a_call_prints_its_declaration_and_its_zod_keys(tmp_path):
    """Planning Tool (5.0 gate, gate-4): `show batchAssignSchema`, an exported zod constant, printed `word matches:
    the 191 lines below only share a word` and 20 unrelated callbacks: no declaration, no range. A JS/TS module-level
    constant whose value is a call prints one line with its place, the value cut to its first call (`z.object(...)`
    of `z.object({...}).strict()`, `requireAtLeastOneValue(...)` of a helper wrapping the object, a `new` expression
    with its type arguments); a zod object adds the zod lines of its number keys, nested ones too; the names that only
    share a word wait for --full."""
    _commit(tmp_path, GB_FILES)
    assignment, personnel = 'backend/src/api/schemas/assignment.schemas.ts', 'backend/src/api/schemas/personnel-mvp.schemas.ts'

    def shown(query, *options):
        code, text = _flowguard(tmp_path, 'show', query, *options)
        assert code == 0 and 'not on the map' not in text, text
        return text.splitlines()
    lines = shown('batchAssignSchema')
    assert lines[2:4] == [f'const batchAssignSchema = z.object(...) ({assignment}:3)',
                          f'zod key fteShare in batchAssignSchema: 0 <= fteShare <= 1 ({assignment}:11)'], lines
    assert len(lines) == 5 and lines[4].startswith('... 2 more lines, 1 of them only shares a word with batchAssignSchema'), lines
    assert not any(line.startswith('word matches') for line in lines), lines
    # --full lists the function that shares a word, after its line
    full = shown('batchAssignSchema', '--full')
    assert full[:4] == lines[:4] and full[4].startswith('word matches: ') and any('assignBatch' in line for line in full[5:]), full
    assert shown('lendingUpdateSchema')[2:4] == [
        f'const lendingUpdateSchema = requireAtLeastOneValue(...) ({personnel}:6)',
        f'zod key fteShare in lendingUpdateSchema: 0 < fteShare <= 1, and a refine that is not read may reject more ({personnel}:9)']
    lines = shown('assignmentCache')
    assert lines[2] == 'const assignmentCache = new Map<string, number>(...) (backend/src/services/assignment.service.ts:1)', lines
    assert not any(line.startswith('zod ') for line in lines), lines


def test_show_of_a_table_column_answers_with_the_prisma_field_mapped_to_it(tmp_path):
    """code-0 (5.0 docs review): `show assignments.fte_share` gave only the SQL column and CHECK lines, and a column only
    a Prisma `@map` declares (Planning Tool's assignments.internal_order_id) or only an upgrade script's ALTER TABLE
    ADD adds got `not on the map: no function, class, ... is named assignments.internal_order_id`. `table.column` now
    answers with the Prisma field `@@map` and `@map` map to it, as `show Model.field` does, and an upgrade script's
    ALTER TABLE ADD gives the column's line."""
    _commit(tmp_path, GB_FILES)
    migration = 'backend/prisma/migrations/20260317073846_init/migration.sql'

    def shown(query):
        code, text = _flowguard(tmp_path, 'show', query, '--full')
        assert code == 0 and 'not on the map' not in text, text
        return text.splitlines()
    lines = shown('assignments.fte_share')
    assert lines[2:6] == ['declared Assignment.fteShare: Decimal @map("fte_share") (backend/prisma/schema.prisma:8)',
                          f'column assignments.fte_share DECIMAL ({migration}:3)',
                          f'range assignments.fte_share: 0 <= fte_share <= 2 (CHECK {migration}:4)',
                          'zod key fteShare in assignmentEditSchema: MIN_FTE_SHARE=0 <= fteShare <= MAX_FTE_SHARE=2.0 '
                          '(backend/src/api/schemas/employee-utilization.schemas.ts:7)'], lines
    # its writes and reads are the Prisma field's, as show Assignment.fteShare lists them
    field = shown('Assignment.fteShare')
    assert [line for line in lines if line.startswith(('writes ', 'reads ', 'zod ', 'the '))] == \
        [line for line in field if line.startswith(('writes ', 'reads ', 'zod ', 'the '))], (lines, field)
    assert 'writes Assignment.fteShare backend/src/services/assignment.service.ts:4 assignBatch (create)' in lines, lines
    assert shown('assignments.internal_order_id')[2] == \
        'declared Assignment.internalOrderId: String? @map("internal_order_id") @db.NVarChar(36) (backend/prisma/schema.prisma:9)'
    assert shown('assignments.legacy_order_code')[2] == \
        'column assignments.legacy_order_code NVARCHAR(20) (backend/prisma/upgrade-internal-orders.sql:1)'


def test_show_of_a_field_marks_the_tests_its_project_runs_against_real_databases_or_leaves_out(tmp_path):
    """Planning Tool (5.0 gate, gate-7): `show Assignment.fteShare` listed backend/tests/integration/* as `test ...
    reaches a writer` like any unit test, though the backend runs that folder only through its "test:integration"
    script, against real databases. A test file in a folder that a test script of its package runs as such a suite
    (init's reading of the scripts), or one the project's test scope leaves out (vitest's test.include and
    test.exclude, pytest's testpaths, python_files and norecursedirs), says so on its line."""
    _commit(tmp_path / 'ts', GB_FILES)
    code, text = _flowguard(tmp_path / 'ts', 'show', 'Assignment.fteShare', '--full')
    assert code == 0, text
    assert [line for line in text.splitlines() if line.startswith('test ')] == [
        'test backend/tests/integration/assignment.routes.test.ts reaches a writer of Assignment.fteShare (a suite that '
        'reaches real databases and services: backend/package.json script "test:integration" runs tests/integration)',
        'test backend/tests/support/seed-assignments.ts reaches a writer of Assignment.fteShare (left out of the test scope: '
        'test.include and test.exclude of backend/vitest.config.mjs do not take it)',
        'test backend/tests/unit/assignment.service.test.ts reaches a writer of Assignment.fteShare'], text
    _commit(tmp_path / 'py', {
        'pyproject.toml': '[tool.pytest.ini_options]\npythonpath = ["."]\ntestpaths = ["tests"]\n',
        'app/__init__.py': '',
        'app/model.py': 'class Account:\n    status: str\n',
        'app/service.py': 'from app.model import Account\n\n\ndef close(account: Account):\n    account.status = "closed"\n',
        'tests/test_service.py': 'from app.service import close\n\n\ndef test_close():\n    assert close is not None\n',
        'legacy/test_close_legacy.py': 'from app.service import close\n\n\ndef test_close():\n    assert close is not None\n',
    })
    code, text = _flowguard(tmp_path / 'py', 'show', 'Account.status', '--full')
    assert code == 0 and [line for line in text.splitlines() if line.startswith('test ')] == [
        "test legacy/test_close_legacy.py reaches a writer of Account.status (left out of the test scope: pytest's testpaths, "
        'python_files and norecursedirs do not take it)',
        'test tests/test_service.py reaches a writer of Account.status'], text


def test_show_of_a_field_marks_each_write_in_a_test_its_project_leaves_out_or_runs_against_real_databases(tmp_path):
    """Planning Tool (5.0 gate, gate-5): only the `test ... reaches a writer` lines, which the default view of `show
    Assignment.fteShare` cuts, said that backend/tests/integration is a suite against real databases; the `writes`
    lines the view does show, `writes Assignment.fteShare backend/tests/integration/dashboard.routes.test.ts:146 (call
    line 141) ensureFixtures (create)`, sat among the production writers with no mark. A write in a test file carries
    the mark its reach line carries; a write in a test the scope takes, and a production write, carry none."""
    fixture = ("import { PrismaClient } from '@prisma/client';\nconst prisma = new PrismaClient();\n"
               "async function ensureFixtures() {\n  await prisma.assignment.create({ data: { id: 'a', fteShare: 0.5 } });\n}\n"
               'export const ready = ensureFixtures;\n')
    _commit(tmp_path, {**GB_FILES, 'backend/tests/integration/dashboard.routes.test.ts': fixture,
                       'backend/tests/unit/fixtures.test.ts': fixture.replace('ensureFixtures', 'unitFixtures')})
    code, text = _flowguard(tmp_path, 'show', 'Assignment.fteShare')
    assert code == 0, text
    assert [line for line in text.splitlines() if line.startswith('writes ')] == [
        'writes Assignment.fteShare backend/src/services/assignment.service.ts:4 assignBatch (create)',
        'writes Assignment.fteShare backend/tests/integration/dashboard.routes.test.ts:4 ensureFixtures (create) (a suite that '
        'reaches real databases and services: backend/package.json script "test:integration" runs tests/integration)',
        'writes Assignment.fteShare backend/tests/unit/fixtures.test.ts:4 unitFixtures (create)'], text


def test_show_of_a_bare_field_name_names_the_prisma_models_that_declare_it(tmp_path):
    """Planning Tool (5.0 re-review, pt-rereview-7): `show fteShare` printed about 37 functions that share a word with it
    and no fact, though the Prisma models Assignment, LendingAssignment and AbsencePhase declare fteShare. A bare field
    name, or its `@map` column, now prints one line naming each model's field as its own view takes it."""
    _commit(tmp_path, {**PT_CAPACITY, 'frontend/src/utils/absence-phase-units.ts':
                       'export function displayValueToFteShare(value: number): number {\n  return value / 100;\n}\n'})
    line = ('Prisma models with a field {}: AbsencePhase.fteShare, Assignment.fteShare, Employee.fteShare (python -m '
            'flowguard show MODEL.FIELD lists the facts of one)')
    for query in ('fteShare', 'fte_share'):
        lines = _shown_lines(tmp_path, query)
        assert lines[2:] == [line.format(query), f'... 2 more lines, 1 of them only shares a word with {query}: python -m '
                             f'flowguard show {query} --full lists them all'], lines
    assert not [line for line in _shown_lines(tmp_path, 'unitTypes') if line.startswith('Prisma models with')]


def test_show_says_in_one_line_when_the_map_knows_no_such_name_and_names_the_nearest_field(tmp_path):
    """Planning Tool (5.0 re-review, pt-rereview-19 and 4): `show zebraQuokka` printed the header and the map notice
    only, `show frobnicate_widget_count` 38 count functions as if they were matches, and `show
    CapacityCalendarEntry.valeu` named no near field. A name the map does not know says so in one line, the names that
    only share a word follow a line that says so, and a misspelt field of a known model names that model's nearest
    field. A Python module constant, a TS interface, a SQL table or column and a phrase are no unknown names."""
    _commit(tmp_path, {**PT_CAPACITY, 'tools/limits.py': 'MAX_IMPORT_ROWS = 500\n',
                       'backend/src/types/employee.types.ts': 'export interface UpdateEmployeeInput {\n  name: string;\n}\n',
                       'backend/prisma/report-views.sql': 'CREATE TABLE report_rows (\n  id INT,\n  booked_hours DECIMAL(10,2)\n);\n'})
    unknown = 'not on the map: no function, class, type, constant, enum, Prisma model or field, or SQL table or column is named {}'
    for query in ('zebraQuokka', 'zebra.quokka'):
        assert _shown_lines(tmp_path, query)[2:] == [unknown.format(query)], query
    lines = _shown_lines(tmp_path, 'frobnicate_widget_count')
    assert lines[2:] == [unknown.format('frobnicate_widget_count'),
                         'word matches: the 2 lines below only share a word with frobnicate_widget_count',
                         'tsx/frontend/src/components/import/ImportResultStep.tsx:CountCard frontend/src/components/import/ImportResultStep.tsx:1',
                         'tsx/frontend/src/components/import/ImportResultStep.tsx:countLeaves frontend/src/components/import/ImportResultStep.tsx:4'], lines
    assert _shown_lines(tmp_path, 'CapacityCalendarEntry.valeu')[2] == (
        'not on the map: Prisma model CapacityCalendarEntry has no field valeu, the nearest field is CapacityCalendarEntry.value')
    assert _shown_lines(tmp_path, 'capacity_calendar_entries.unit_tpye')[2] == (
        'not on the map: Prisma model CapacityCalendarEntry (table capacity_calendar_entries) and database table '
        'capacity_calendar_entries have no field or column unit_tpye, the nearest is capacity_calendar_entries.unit_type')
    # a field far from every field of the model names none
    assert _shown_lines(tmp_path, 'CapacityCalendarEntry.approvedBy')[2] == (
        'not on the map: Prisma model CapacityCalendarEntry has no field approvedBy')
    for query in ('MAX_IMPORT_ROWS', 'UpdateEmployeeInput', 'booked_hours', 'report_rows', 'percent hours'):
        assert not [line for line in _shown_lines(tmp_path, query) if line.startswith('not on the map')], query


PT_HOLDERS = {
    'backend/src/services/lending.service.ts': """import { prisma } from '../lib/prisma';

const LENDING_LIMIT = 1;

/** Lending of employees between units. */
export const lendingService = {
  /** Every lending of an employee. */
  async listLendings(employeeId: string) {
    return prisma.lending.findMany({ where: { employeeId } });
  },
  async createLending(employeeId: string, share: number) {
    return prisma.lending.create({ data: { employeeId, share } });
  },
  async endLending(id: string) {
    return prisma.lending.update({ where: { id }, data: { endDate: new Date() } });
  },
  async extendLending(id: string, endDate: Date) {
    return prisma.lending.update({ where: { id }, data: { endDate } });
  },
  async removeLending(id: string) {
    return prisma.lending.delete({ where: { id } });
  },
};
""",
    'backend/src/services/import.service.ts': """export class ImportService {
  constructor(private readonly limit: number) {}

  async commitProjects(rows: string[]) {
    return rows.length <= this.limit;
  }
}
""",
}


PT_CALENDAR_WRITERS = {
    'backend/prisma/schema.prisma': PT_CAPACITY['backend/prisma/schema.prisma'],
    'backend/src/services/capacity.service.ts': PT_CAPACITY['backend/src/services/capacity.service.ts'],
    'backend/src/services/employee-utilization.service.ts': """export const employeeUtilizationService = {
  async batchSaveUtilization(prisma: any, rows: any[]) {
    const persist = async (row: any) => prisma.capacityCalendarEntry.create({ data: { id: row.id, value: row.value } });
    for (const row of rows) {
      await persist(row);
    }
  },
};
""",
    'backend/src/services/migration.service.ts': """export async function importPersonnelCapacityEntries(prisma: any, rows: any[]) {
  return prisma.capacityCalendarEntry.createMany({ data: rows.map((row) => ({ id: row.id, value: row.value })) });
}
""",
    'backend/src/services/import.service.ts': """export class ImportService {
  async commitCapacity(prisma: any, id: string, value: number) {
    return prisma.capacityCalendarEntry.update({ where: { id }, data: { value } });
  }
}
""",
}


def test_the_writers_comment_a_structure_line_suggests_is_one_the_check_reads(tmp_path):
    """pt-smoke-0 (2026-11): `show CapacityCalendarEntry.value` on Planning Tool suggested `// flowguard: writers
    CapacityCalendarEntry.value backend/src/services/capacity.service.ts:updateCalendarEntry,...`; pasted unchanged,
    `check --static` gave `1 red: ... cannot resolve typescript/backend/src/services/capacity.service.ts:
    updateCalendarEntry to one declared function`, as updateCalendarEntry is a method of the object literal
    capacityService. The step now spells each writer as the comment reader resolves it (`path:object.method`, a class's
    `path:Class.method`, a nested function as declared), and the suggested comment, pasted, gives 0 red."""
    _commit(tmp_path, PT_CALENDAR_WRITERS)
    code, text = _flowguard(tmp_path, 'show', 'CapacityCalendarEntry.value')
    [line] = [line for line in text.splitlines() if line.startswith('structure: ')]
    comment = re.search(r'write (// flowguard: writers \S+ \S+) with only', line)[1]
    assert comment == (
        '// flowguard: writers CapacityCalendarEntry.value '
        'backend/src/services/capacity.service.ts:capacityService.updateCalendarEntry,'
        'backend/src/services/employee-utilization.service.ts:batchSaveUtilization.persist,'
        'backend/src/services/import.service.ts:ImportService.commitCapacity,'
        'backend/src/services/migration.service.ts:importPersonnelCapacityEntries'), line
    capacity = tmp_path / 'backend/src/services/capacity.service.ts'
    capacity.write_text(comment + '\n' + capacity.read_text(encoding='utf-8'), encoding='utf-8')
    code, text = _flowguard(tmp_path, 'check', '--static')
    assert code == 0 and ' 0 red' in text.splitlines()[0] and not [line for line in text.splitlines()
                                                                  if line.startswith('red')], text


def test_show_of_an_object_or_class_that_holds_methods_names_it_its_place_and_its_methods(tmp_path):
    """K3-0 (2026-11): on Planning Tool `show capacityService` and `show employeeService` said `not on the map: no
    function, class, ... is named capacityService`, though `export const capacityService = {` holds the methods
    that `show capacityService.updateCalendarEntry` finds. An object literal or a class that holds methods is a name the
    map knows: one line names it, its place and its methods, before the word matches."""
    _commit(tmp_path, {**PT_CAPACITY, **PT_HOLDERS})
    lines = _shown_lines(tmp_path, 'capacityService')
    assert lines[2:4] == [
        'object capacityService (backend/src/services/capacity.service.ts:1): 2 methods: updateCalendarEntry, '
        'listCalendarEntries (python -m flowguard show capacityService.METHOD prints one)',
        '... 20 more lines, 19 of them only share a word with capacityService: python -m flowguard show capacityService '
        '--full lists them all'], lines
    lines = _shown_lines(tmp_path, 'lendingService')
    assert lines[2] == ('object lendingService (backend/src/services/lending.service.ts:6): 5 methods: listLendings, '
                        'createLending, endLending and 2 more (python -m flowguard show lendingService.METHOD prints one)'), lines
    assert not [line for line in lines if line.startswith(('not on the map', 'word matches'))], lines
    assert _shown_lines(tmp_path, 'lendingService', '--full')[2].startswith(
        'object lendingService (backend/src/services/lending.service.ts:6): 5 methods: listLendings, createLending, '
        'endLending, extendLending, removeLending (')
    lines = _shown_lines(tmp_path, 'ImportService')
    assert ('class ImportService (backend/src/services/import.service.ts:1): 2 methods: constructor, commitProjects '
            '(python -m flowguard show ImportService.METHOD prints one)') in lines, lines


PT_API_HOLDERS = {
    # Planning Tool's frontend API objects: every member an arrow function (32 `export const xApi = {` files), and
    # authSessionApi mixing a method with arrow members.
    'frontend/package.json': '{"name": "frontend", "type": "module"}',
    'frontend/src/services/api/demand.api.ts': """import { apiClient } from './client';

export const demandApi = {
  getAll: (params?: Record<string, string | number>) =>
    apiClient.get('/api/demands', { params }).then((r) => r.data),

  getById: (id: string) =>
    apiClient.get(`/api/demands/${id}`).then((r) => r.data.data),

  cancel: async function (id: string) {
    return apiClient.post(`/api/demands/${id}/cancel`, {});
  },
};
""",
    'frontend/src/services/api/client.ts': """export const apiClient = {
  get: (url: string, options?: unknown) => fetch(url).then((response) => ({ data: { data: options, url } })),
  post: (url: string, body: unknown) => fetch(url, { method: 'POST', body: JSON.stringify(body) }),
};
""",
    'frontend/src/services/api/developer-login.api.ts': """import { apiClient } from './client';

function mutateAuth(path: string, body: unknown) {
  return apiClient.post(path, body);
}

/** Cookie transitions reject on CSRF, permission or stale-session errors. */
export const authSessionApi = {
  /** Restore phase. */
  async me() {
    return (await apiClient.get('/auth/me')).data.data;
  },
  /** Verify credentials. */
  login: (email: string, password: string) => mutateAuth('/auth/login', { email, password }),
  /** Revoke cookies. */
  logout: () => mutateAuth('/auth/logout', {}),
  /** Activate target. */
  select: (employeeId: string, revision: number) =>
    mutateAuth('/auth/dev-login/select', { employeeId, revision }),
  /** Invalidate target. */
  changeUser: () => mutateAuth('/auth/dev-login/change-user', {}),
  /** Toggle target's admin mode. */
  adminMode: (enabled: boolean) => mutateAuth('/auth/admin-mode', { enabled }),
};
""",
    'frontend/src/pages/demands.ts': """import { demandApi } from '../services/api/demand.api';

export async function loadDemands(page: number) {
  return demandApi.getAll({ page });
}
""",
    'backend/src/services/session-store.ts': """export const SessionStore = class SessionStore {
  read(id: string) { return id; }
};

export const Registry = class Store {
  run() { return 1; }
  handle = (id: string) => id;
};
""",
}


def test_a_holder_counts_every_function_valued_member_and_show_finds_each(tmp_path):
    """Z-1 (2026-11): K3-0's holder line counted only method definitions. On Planning Tool `show authSessionApi` said
    `1 method: me` of an object with six function members, and `show demandApi` (32 such `export const xApi = {`
    files, every member an arrow function) printed no holder line, while `show demandApi.getAll` said `not on the map`:
    the map held those members as `<anonymous@33,11>` with no holder. A holder's count and list are every
    function-valued member (method definitions, arrow functions and function expressions as properties or class
    fields), the same members `show holder.member` finds. Z-2: a named class expression (`const SessionStore = class
    SessionStore {`, `const Registry = class Store {`) crashed show with StopIteration; its place comes from the map."""
    _commit(tmp_path, PT_API_HOLDERS)
    lines = _shown_lines(tmp_path, 'authSessionApi')
    assert lines[2] == ('object authSessionApi (frontend/src/services/api/developer-login.api.ts:8): 6 methods: me, login, '
                        'logout and 3 more (python -m flowguard show authSessionApi.METHOD prints one)'), lines
    assert _shown_lines(tmp_path, 'authSessionApi', '--full')[2].startswith(
        'object authSessionApi (frontend/src/services/api/developer-login.api.ts:8): 6 methods: me, login, logout, select, '
        'changeUser, adminMode (')
    lines = _shown_lines(tmp_path, 'demandApi')
    assert lines[2] == ('object demandApi (frontend/src/services/api/demand.api.ts:3): 3 methods: getAll, getById, cancel '
                        '(python -m flowguard show demandApi.METHOD prints one)'), lines
    # Each member the line counts is found by holder.member, with its node view and its caller.
    for member, line in (('getAll', 4), ('getById', 7), ('cancel', 10)):
        lines = _shown_lines(tmp_path, f'demandApi.{member}')
        assert not [item for item in lines if item.startswith('not on the map')], lines
        assert lines[2].endswith(f' frontend/src/services/api/demand.api.ts:{line}'), lines
    assert 'called by 1 function through a resolved call: loadDemands (frontend/src/pages/demands.ts:3)' in \
        _shown_lines(tmp_path, 'demandApi.getAll'), _shown_lines(tmp_path, 'demandApi.getAll')
    lines = _shown_lines(tmp_path, 'authSessionApi.logout')
    assert lines[2].endswith(' frontend/src/services/api/developer-login.api.ts:16'), lines
    # A class expression: the class it names, at its place; a class field holding a function is a member too.
    lines = _shown_lines(tmp_path, 'SessionStore')
    assert ('class SessionStore (backend/src/services/session-store.ts:1): 1 method: read '
            '(python -m flowguard show SessionStore.METHOD prints one)') in lines, lines
    lines = _shown_lines(tmp_path, 'Store')
    assert ('class Store (backend/src/services/session-store.ts:5): 2 methods: run, handle '
            '(python -m flowguard show Store.METHOD prints one)') in lines, lines
    # An unnamed class expression is held under the name its declaration gives it (const Anon = class {...}).
    _write(tmp_path, {'backend/src/services/anon.ts': 'export const Anon = class {\n  m() { return 1; }\n};\n'})
    lines = _shown_lines(tmp_path, 'Anon')
    assert ('class Anon (backend/src/services/anon.ts:1): 1 method: m '
            '(python -m flowguard show Anon.METHOD prints one)') in lines, lines
    assert _shown_lines(tmp_path, 'Anon.m')[2].endswith(' backend/src/services/anon.ts:2'), _shown_lines(tmp_path, 'Anon.m')


def test_the_count_show_gives_without_full_is_what_full_adds(tmp_path):
    """Planning Tool (5.0 re-review, pt-rereview-3): `show CapacityCalendarEntry.value` ended `... 67 more lines`, but
    --full printed 1048 lines more: the count left out the names that wait for --full and counted their own line as
    one. The last line now counts every line --full adds below the last line shown, the line that says the rest only
    share a word included; the last run's lines that their own count line counts are not counted again, unless that
    line is cut away too."""
    fields = ['name', 'email', 'firstName', 'surname', 'startDate', 'endDate', 'resourceTypeId']
    data = ', '.join(f'{field}: input.{field}' for field in fields)
    _commit(tmp_path, {
        'pyproject.toml': '[tool.flowguard]\nscreen_lines = 6\n',
        'backend/prisma/schema.prisma': 'datasource db {\n  provider = "sqlserver"\n  url      = env("DATABASE_URL")\n}\n\n'
                                        'model Employee {\n  id String @id\n' + ''.join(f'  {field} String\n' for field in fields)
                                        + '  @@map("employees")\n}\n',
        # three files write each field without a writers agreement: seven last-run lines at employeeService.update
        'backend/src/services/employee.service.ts': ('export const employeeService = {\n  async update(prisma: any, id: string, '
                                                     f'input: any) {{\n    return prisma.employee.update({{ where: {{ id }}, data: '
                                                     f'{{ {data} }} }});\n  }},\n}};\n'),
        'backend/src/services/import.service.ts': ('export async function importEmployees(prisma: any, input: any) {\n  return '
                                                   f'prisma.employee.create({{ data: {{ id: input.id, {data} }} }});\n}}\n'),
        'backend/src/services/sync.service.ts': ('export async function syncEmployees(prisma: any, input: any) {\n  return '
                                                 f'prisma.employee.update({{ where: {{ id: input.id }}, data: {{ {data} }} }});\n}}\n'),
        'backend/src/services/employee-update.helpers.ts': 'export function updateLabel(id: string) {\n  return id;\n}\n',
    })

    def counted(query):
        lines, full = _shown_lines(tmp_path, query), _shown_lines(tmp_path, query, '--full')
        return lines, full, int(lines[-1].split()[1])
    # facts cut by the screen, and the names that only share a word, which wait for --full
    lines, full, count = counted('Employee.email')
    assert len(lines) == 6 and count == len(full) - 5 == 10, (lines, full)
    assert full[-3] == 'word matches: the 2 lines below only share a word with Employee.email', full
    assert lines[-1] == ('... 10 more lines, 2 of them only share a word with Employee.email: python -m flowguard show '
                         'Employee.email --full lists them all'), lines
    # the last run's count line cut away: --full adds its lines too
    code, text = _flowguard(tmp_path, 'check', '--static', '--all')
    assert code == 0 and 'Employee.email has no writers agreement and 3 files write it, employee.service.ts:update among them' in text, text
    lines, full, count = counted('employeeService.update')
    assert lines[2:5] == [f'before (last run): Employee.{field} has no writers agreement and 3 files write it, '
                          'backend/src/services/employee.service.ts:update among them; so at task start -> leave it unless '
                          'your task is about it' for field in ('email', 'endDate', 'firstName')], lines
    assert count == len(full) - 5 == 12, (lines, full)
    # shown, it counts its own lines: the last line counts the rest
    (tmp_path / 'pyproject.toml').write_text('[tool.flowguard]\nscreen_lines = 9\n', encoding='utf-8')
    lines, full, count = counted('employeeService.update')
    assert lines[7] == ('... 2 more lines of the last run there: python -m flowguard show employeeService.update --full '
                        'lists them all') and count == len(full) - 8 - 2 + 1 == 8, (lines, full)


READ_SETTINGS = '''
from dataclasses import asdict, dataclass, replace


@dataclass
class Settings:
    appearance: str = "light"

    def __post_init__(self):
        pass


@dataclass
class Controller:
    settings: Settings


class SettingsDialog:
    def __init__(self):
        self.appearance = "dialog"


def direct(settings: Settings):
    return settings.appearance


def chained(controller: Controller):
    return controller.settings.appearance


def aliased(controller: Controller):
    settings = controller.settings
    return settings.appearance


def serialized(settings: Settings):
    return asdict(settings)


def replacement(settings: Settings):
    return replace(settings, appearance="dark")


def dialog_appearance(dialog: SettingsDialog):
    return dialog.appearance


def untyped(settings):
    return settings.appearance
'''


def test_a_python_field_s_impact_line_counts_the_functions_that_read_it_and_says_what_it_leaves_out(tmp_path):
    """PYREAD18-1, PYREAD18-2 (PEMEL Studio, 2026-11-18): `Settings.__post_init__ now writes Settings.appearance; 0
    other writers, 0 readers of Settings`, while the app read it directly, through a chained attribute, a local alias
    and asdict. 5.0.1 counted only Prisma and SQL readers. A read through an untyped name is not counted, and the line
    says so; the dialog's field of the same name is another class's."""
    _commit(tmp_path, {'app/__init__.py': '', 'app/settings.py': READ_SETTINGS})
    _write(tmp_path, {'app/settings.py': READ_SETTINGS.replace('        pass\n',
                                                               '        self.appearance = self.appearance.strip()\n')})
    found, modules = _impact(tmp_path)
    module = modules['app/settings.py']
    [line] = found.lines
    assert line.text == ('Settings.__post_init__ now writes Settings.appearance; 0 other writers, 5 readers (untyped '
                         'reads not counted)'), line.text
    assert line.step == 'check them for this change only (python -m flowguard show Settings.appearance)'
    assert line.detail == tuple(f'reader of Settings.appearance: {module}:{function}' for function in (
        'Settings.__post_init__', 'aliased', 'chained', 'direct', 'serialized')), line.detail
    lines = _shown_lines(tmp_path, 'Settings.appearance', '--full')
    reads = [line for line in lines if line.startswith('reads ')]
    assert reads == ['reads Settings.appearance app/settings.py:9 Settings.__post_init__ (attribute)',
                     'reads Settings.appearance app/settings.py:23 direct (attribute)',
                     'reads Settings.appearance app/settings.py:27 chained (attribute)',
                     'reads Settings.appearance app/settings.py:32 aliased (attribute)',
                     'reads Settings.appearance app/settings.py:36 serialized (asdict)'], lines
    assert 'reads SettingsDialog.appearance app/settings.py:44 dialog_appearance (attribute)' in \
        _shown_lines(tmp_path, 'SettingsDialog.appearance', '--full')
    # a database model's readers keep their wording: test_a_changed_function_whose_written_fields_changed_gets_...


PANE = '''
from functools import cached_property


class Pane:
    def __init__(self):
        self._hovered = False

    def enter(self):
        self._hovered = True

    @property
    def highlighted(self):
        return self._hovered

    @cached_property
    def label(self):
        return 'pane'

    def describe(self):
        self.enter()
        return 'hovered' if self._hovered else 'idle'
'''


def test_reads_through_self_count_and_a_property_view_lists_who_reads_it(tmp_path):
    """PEMEL23-5a, PEMEL23-5b (four PEMEL agents): `Pane.__init__ now writes Pane._pressed; 0 other writers, 0 readers
    of Pane`, while its own pressed() read it; `show Pane._hovered` listed only its writes, and `show Pane.highlighted`
    only `called by no function`, as reading a property calls nothing."""
    _commit(tmp_path, {'app/__init__.py': '', 'app/pane.py': PANE,
                       'app/badge.py': 'from app.pane import Pane\n\n\ndef badge(pane: Pane):\n    return pane.highlighted\n',
                       'tests/test_pane.py': 'from app.pane import Pane\n\n\ndef test_one():\n    p = Pane()\n    p.enter()\n'
                                             '    assert p.highlighted\n'})
    _write(tmp_path, {'app/pane.py': PANE.replace('        self._hovered = False\n',
                                                  '        self._hovered = False\n        self._pressed = False\n')
                      + '\n    def pressed(self):\n        return self._pressed\n'})
    found, modules = _impact(tmp_path)
    [line] = found.lines
    assert line.text == 'Pane.__init__ now writes Pane._pressed; 0 other writers, 1 reader (untyped reads not counted)'
    assert line.detail == (f'reader of Pane._pressed: {modules["app/pane.py"]}:Pane.pressed',)
    lines = _shown_lines(tmp_path, 'Pane._hovered', '--full')
    assert [line for line in lines if line.startswith(('writes ', 'reads '))] == [
        'writes Pane._hovered app/pane.py:6 Pane.__init__ (assign)',
        'writes Pane._hovered app/pane.py:10 Pane.enter (assign)',
        'reads Pane._hovered app/pane.py:14 Pane.highlighted (attribute)',
        'reads Pane._hovered app/pane.py:22 Pane.describe (attribute)'], lines
    # A property: the functions that read it as an attribute (the test's `p = Pane()` is untyped); one read by none
    # says so. A method called through self is called, not read.
    for query in ('Pane.highlighted', 'app/pane.py:Pane.highlighted'):
        lines = _shown_lines(tmp_path, query)
        assert 'read as an attribute by 1 function (untyped reads not counted): badge (app/badge.py:5)' in lines, lines
    assert ('read as an attribute by no function through self, cls, an annotated name or a declared field (untyped reads '
            'not counted)') in _shown_lines(tmp_path, 'Pane.label'), lines
    assert not [line for line in _shown_lines(tmp_path, 'Pane.enter') if line.startswith('read as an attribute')]


def test_show_of_a_field_this_change_stopped_writing_lists_its_writes_and_reads_at_the_task_start(tmp_path):
    """PEMEL23-6c: `impact: Pane.__init__ now writes Pane.ui; no longer writes Pane.title; ...` pointed at `show
    Pane.title`, which printed `not on the map` and words: nothing about the write this change removed or who read
    the field."""
    panel = ('from app.text import render_ui_text\n\n\nclass Pane:\n    def __init__(self):\n'
             '        self.title = render_ui_text("x")\n\n    def label(self):\n        return [self.title]\n')
    _commit(tmp_path, {'app/__init__.py': '', 'app/panel.py': panel,
                       'app/text.py': 'def render_ui_text(t):\n    return t.upper()\n'})
    _write(tmp_path, {'app/panel.py': panel.replace('self.title', 'self.ui')})
    lines = _shown_lines(tmp_path, 'Pane.title')
    assert lines[1:4] == [
        'not on the map: no function, class, type, constant, enum, Prisma model or field, or SQL table or column is named '
        'Pane.title',
        'writes Pane.title app/panel.py:6 Pane.__init__ (assign) at the task start',
        'reads Pane.title app/panel.py:9 Pane.label (attribute) at the task start'], lines
    # a field the code writes now shows the code now only
    assert not [line for line in _shown_lines(tmp_path, 'Pane.ui', '--full') if line.endswith('at the task start')]


PANEL = '''class PaneHandle:
    def __init__(self):
        self._hovered = False

    @property
    def highlighted(self):
        return self._hovered

    def paintEvent(self, event):
        if self.highlighted:
            return 1

    def tip(self):
        return self.highlighted


class Controller:
    def request_close(self):
        return not self._closing_window
'''


def test_show_lists_a_task_start_read_only_for_a_function_that_no_longer_reads_the_field(tmp_path):
    """Round A of 5.1: on a tree with no change since new-task, `show PaneHandle.highlighted` (a @property) and `show
    Controller._closing_window` (an attribute only read, PEMEL23-5a/5b) printed each read twice, the second `at the
    task start`, and once lines had shifted that line named a stale line number. A task-start read is listed only for a
    function that no longer reads the field now, compared by function and kind, never by line."""
    _commit(tmp_path, {'shell/__init__.py': '', 'shell/project_panel.py': PANEL})
    started, text = _flowguard(tmp_path, 'new-task')
    assert started == 0, text
    reads = lambda query: [line for line in _shown_lines(tmp_path, query) if line.startswith('reads ')]
    assert reads('PaneHandle.highlighted') == [
        'reads PaneHandle.highlighted shell/project_panel.py:10 PaneHandle.paintEvent (attribute)',
        'reads PaneHandle.highlighted shell/project_panel.py:14 PaneHandle.tip (attribute)']
    assert reads('Controller._closing_window') == [
        'reads Controller._closing_window shell/project_panel.py:19 Controller.request_close (attribute)']
    # an edit that only shifts the lines: each read once, at its line now
    _write(tmp_path, {'shell/project_panel.py': '# a\n# b\n# c\n' + PANEL})
    assert reads('PaneHandle.highlighted') == [
        'reads PaneHandle.highlighted shell/project_panel.py:13 PaneHandle.paintEvent (attribute)',
        'reads PaneHandle.highlighted shell/project_panel.py:17 PaneHandle.tip (attribute)']
    # a function that no longer reads it keeps its task-start line, the one that still reads it does not
    _write(tmp_path, {'shell/project_panel.py': PANEL.replace('        return self.highlighted\n', '        return None\n')})
    assert reads('PaneHandle.highlighted') == [
        'reads PaneHandle.highlighted shell/project_panel.py:10 PaneHandle.paintEvent (attribute)',
        'reads PaneHandle.highlighted shell/project_panel.py:14 PaneHandle.tip (attribute) at the task start']


def test_the_impact_detail_names_ten_readers_and_counts_the_rest(tmp_path):
    readers = ''.join(f'\n\ndef read_{n}(job: Job):\n    return job.state\n' for n in range(12))
    base = 'class Job:\n    def __init__(self):\n        self.code = 0\n' + readers
    _commit(tmp_path, {'app/__init__.py': '', 'app/job.py': base})
    _write(tmp_path, {'app/job.py': base.replace('self.code = 0', 'self.code = 0\n        self.state = "new"')})
    found, modules = _impact(tmp_path)
    [line] = found.lines
    assert line.text == 'Job.__init__ now writes Job.state; 0 other writers, 12 readers (untyped reads not counted)'
    assert line.detail == (*(f'reader of Job.state: {modules["app/job.py"]}:read_{n}' for n in (0, 1, 10, 11, 2, 3, 4, 5, 6, 7)),
                           '2 more readers of Job.state: python -m flowguard show Job.state --full lists them'), line.detail


# ---- what a field line says of a field a function no longer writes (U11) ----------------------------------------

MOVED_SCHEMA = '''
model AbsenceRecord {
  id     Int @id @default(autoincrement())
  status String
  phases AbsencePhase[]
}

model AbsencePhase {
  id              Int    @id @default(autoincrement())
  absenceRecordId Int
  startDate       DateTime
  endDate         DateTime
  share           Float
  absence         AbsenceRecord @relation(fields: [absenceRecordId], references: [id])
}

model ProjectRequest {
  id        Int @id @default(autoincrement())
  orgUnitId Int
}

model ProjectMember {
  id        Int @id @default(autoincrement())
  projectId Int
  userId    Int
  active    Boolean
}

model Assignment {
  id     Int    @id @default(autoincrement())
  status String
  userId Int
}
'''


def _absence_ts(data):
    return f'''import {{ prisma }} from './db';

export async function update(id: number, phases: {{ startDate: Date; endDate: Date; share: number }}[]) {{
  await prisma.$transaction(async (tx) => {{
    await tx.absenceRecord.update({{ where: {{ id }}, data: {{ status: 'OPEN' }} }});
    await tx.absencePhase.createMany({{ data: phases.map((phase) => ({data})) }});
  }});
}}

export async function readPhases(id: number) {{
  return prisma.absencePhase.findMany({{ where: {{ absenceRecordId: id }} }});
}}
'''


def _members_ts(body, imports=''):
    return f'''{imports}import {{ prisma }} from './db';

export async function assignProjectManager(projectId: number, userId: number, deps: any) {{
  await prisma.$transaction(async (tx) => {{
    await tx.projectMember.updateMany({{ where: {{ projectId }}, data: {{ active: false }} }});
    {body}
  }});
}}

export async function listMembers(projectId: number) {{
  return prisma.projectMember.findMany({{ where: {{ projectId }} }});
}}
'''


MEMBER_HELPER = '''export async function reactivateOrCreateMember(tx: any, projectId: number, userId: number) {
  await tx.projectMember.create({ data: { projectId, userId, active: true } });
}
'''
MOVED_BASE = {
    'prisma/schema.prisma': MOVED_SCHEMA,
    'src/db.ts': 'export const prisma: any = {};\n',
    'src/absence.ts': _absence_ts('{ startDate: phase.startDate, endDate: phase.endDate, share: phase.share, absenceRecordId: id }'),
    'src/members.ts': _members_ts('await tx.projectMember.create({ data: { projectId, userId, active: true } });'),
    'src/registry.ts': '''import { prisma } from './db';

export async function countRequests(orgUnitId: number) {
  return prisma.projectRequest.count({ where: { orgUnitId } });
}
''',
}


def test_a_field_still_written_through_data_whose_fields_are_not_visible_is_not_said_to_be_no_longer_written(tmp_path):
    """PTWF-FIa (Planning Tool): `phases.map((phase) => ({ startDate: phase.startDate, ... }))` became `({ ...phase,
    absenceRecordId: id })`, and 5.0.1 said `update no longer writes AbsencePhase.endDate, AbsencePhase.share,
    AbsencePhase.startDate`, while `show AbsencePhase.endDate` listed that write as `AbsencePhase.?` (`phase is a
    parameter`): the fields may still be among the spread's. A field really dropped from the literal is no longer
    written."""
    _commit(tmp_path, MOVED_BASE)
    _write(tmp_path, {'src/absence.ts': _absence_ts('{ ...phase, absenceRecordId: id }')})
    found, modules = _impact(tmp_path)
    [line] = found.lines
    assert (line.kind, line.function) == ('impact', modules['src/absence.ts'] + ':update')
    assert line.text == ('update writes AbsencePhase.? where it wrote endDate, share, startDate (fields not visible: phase '
                         'is a parameter); 0 other writers, 1 reader of AbsencePhase'), line.text
    assert 'no longer writes' not in line.text
    assert line.step == 'check them for this change only (python -m flowguard show AbsencePhase.endDate)'
    _write(tmp_path, {'src/absence.ts': _absence_ts('{ startDate: phase.startDate, share: phase.share, absenceRecordId: id }')})
    [line] = _impact(tmp_path)[0].lines
    assert line.text == 'update no longer writes AbsencePhase.endDate; 0 other writers, 1 reader of AbsencePhase', line.text


def test_writes_moved_into_a_helper_the_function_calls_are_one_line_and_an_unresolved_call_keeps_two(tmp_path):
    """PTWF-V125 (Planning Tool): `assignProjectManager no longer writes ProjectMember.projectId, ProjectMember.userId`
    beside `reactivateOrCreateMember now writes ProjectMember.active, ...`, two lines that did not say that the one
    calls the other. A call the map resolves links them in one line, naming the helper's other callers; a call it does
    not resolve (through a parameter) links nothing."""
    _commit(tmp_path, {**MOVED_BASE, 'src/member-helpers.ts': '// helpers\n',
                       'src/other.ts': "export async function other(tx: any) {\n  return tx;\n}\n"})
    _write(tmp_path, {'src/member-helpers.ts': MEMBER_HELPER,
                      'src/members.ts': _members_ts('await reactivateOrCreateMember(tx, projectId, userId);',
                                                 "import { reactivateOrCreateMember } from './member-helpers';\n")})
    found, modules = _impact(tmp_path)
    caller = modules['src/members.ts'] + ':assignProjectManager'
    [line] = found.lines
    assert (line.kind, line.name, line.function) == ('impact', 'impact:' + caller, caller)
    assert line.text == ("assignProjectManager's writes of ProjectMember.projectId, ProjectMember.userId moved to "
                         'reactivateOrCreateMember, which it calls (src/member-helpers.ts:1); 0 other writers, 1 reader '
                         'of ProjectMember'), line.text
    assert line.places == ('src/members.ts:assignProjectManager', 'src/member-helpers.ts:1')
    assert line.detail == (
        'assignProjectManager calls reactivateOrCreateMember at src/members.ts:7',
        'reactivateOrCreateMember now writes ProjectMember.active, ProjectMember.projectId, ProjectMember.userId',
        'no other caller of reactivateOrCreateMember through a call the map resolved',
        f'reader of ProjectMember: {caller.rpartition(":")[0]}:listMembers'), line.detail
    # Another function that calls the helper is named on the line.
    _write(tmp_path, {'src/other.ts': "import { reactivateOrCreateMember } from './member-helpers';\n\n"
                                      'export async function other(tx: any) {\n  return reactivateOrCreateMember(tx, 1, 2);\n}\n'})
    [line] = _impact(tmp_path)[0].lines
    assert '(src/member-helpers.ts:1); other callers of reactivateOrCreateMember: other; 0 other writers' in line.text, line.text
    assert f'other caller of reactivateOrCreateMember: {modules["src/other.ts"]}:other' in line.detail, line.detail
    # Called through a parameter, the call is not resolved: two lines, as 5.0.1 gave them.
    _write(tmp_path, {'src/members.ts': _members_ts('await deps.reactivateOrCreateMember(tx, projectId, userId);')})
    found, _ = _impact(tmp_path)
    assert sorted(line.text for line in found.lines) == [
        'assignProjectManager no longer writes ProjectMember.projectId, ProjectMember.userId; 1 other writer, 1 reader of '
        'ProjectMember',
        'reactivateOrCreateMember now writes ProjectMember.active, ProjectMember.projectId, ProjectMember.userId; 1 other '
        'writer, 1 reader of ProjectMember'], [line.text for line in found.lines]


def test_a_python_function_whose_writes_moved_into_a_private_helper_it_calls_gets_one_line(tmp_path):
    """PEMEL17-18 (PEMEL Studio): set_default's writes moved into `_apply`, which it calls, and 5.0.1 gave `_apply now
    writes Prefs.model; 1 other writer, ...` and `set_default no longer writes Prefs.model; 2 other writers, ...`."""
    base = ('class Prefs:\n    def __init__(self):\n        self.model = ""\n        self.revision = 0\n\n\n'
            'def set_default(prefs: Prefs, name):\n    prefs.model = name\n    prefs.revision += 1\n\n\n'
            'def show(prefs: Prefs):\n    return prefs.model\n')
    _commit(tmp_path, {'pyproject.toml': '[project]\nname = "mv"\nversion = "0"\n', 'model.py': base})
    _write(tmp_path, {'model.py': base.replace(
        'def set_default(prefs: Prefs, name):\n',
        'def _apply(prefs: Prefs, name):\n').replace(
        '\n\ndef show', '\n\ndef set_default(prefs: Prefs, name):\n    _apply(prefs, name)\n\n\ndef show')})
    found, modules = _impact(tmp_path)
    [line] = found.lines
    assert line.function == 'model:set_default'
    assert line.text == ("set_default's writes of Prefs.model moved to _apply, which it calls (model.py:7); 1 other "
                         'writer, 1 reader (untyped reads not counted)'), line.text
    assert line.detail == ('set_default calls _apply', '_apply now writes Prefs.model',
                           'no other caller of _apply through a call the map resolved',
                           'other writer of Prefs.model: model:Prefs.__init__', 'reader of Prefs.model: model:show'), line.detail
    code, text = _flowguard(tmp_path, 'check', '--static', '--base', 'HEAD')
    assert code == 0 and text.count('impact: ') == 1 and '_apply now writes' not in text, text


def test_the_block_line_of_writes_moved_to_a_helper_keeps_what_moved_where_with_the_planning_tool_names(tmp_path):
    """PTWF-V125 (5.1 review): with Planning Tool's names the block cut the moved line's middle to 200 characters,
    `impact: assignProjectManager's wr...eMember, which it calls (member-helpers.ts:1); other callers of react...1
    reader of ProjectMember -> ...`, so the line agents read no longer said what moved where. That clause stays whole;
    the other callers and the counts give way first, then the fields are counted. `show --last` keeps every word."""
    helper = {'src/member-helpers.ts': MEMBER_HELPER,
              'src/invite.ts': "import { reactivateOrCreateMember } from './member-helpers';\nimport { prisma } from './db';\n\n"
                               'export async function inviteMember(projectId: number, userId: number) {\n'
                               '  await prisma.$transaction(async (tx) => {\n'
                               '    await reactivateOrCreateMember(tx, projectId, userId);\n  });\n}\n'}
    _commit(tmp_path, {**MOVED_BASE, **helper})
    _write(tmp_path, {'src/members.ts': _members_ts('await reactivateOrCreateMember(tx, projectId, userId);',
                                                    "import { reactivateOrCreateMember } from './member-helpers';\n")})
    code, text = _flowguard(tmp_path, 'check', '--static', '--base', 'HEAD')
    assert code == 0 and "impact: assignProjectManager's writes of 2 ProjectMember fields moved to reactivateOrCreateMember, " \
        'which it calls (member-helpers.ts:1); ... -> check them for this change only (python -m flowguard show ' \
        'ProjectMember.projectId)' in text.splitlines(), text
    code, text = _flowguard(tmp_path, 'show', '--last')
    assert "impact: assignProjectManager's writes of ProjectMember.projectId, ProjectMember.userId moved to " \
        'reactivateOrCreateMember, which it calls (src/member-helpers.ts:1); other callers of reactivateOrCreateMember: ' \
        'inviteMember; 0 other writers, 1 reader of ProjectMember' in text, text


PEMEL_PREFERENCES = '''from dataclasses import dataclass


@dataclass
class ModelPreferences:
    default_model: str = ""
    default_source: str = ""


def set_default_model(preferences: ModelPreferences, model: str, source: str):
    preferences.default_model = model
    preferences.default_source = source


def describe(preferences: ModelPreferences):
    return preferences.default_model
'''


def _pemel_moved(call):
    """PEMEL_PREFERENCES with set_default_model's writes moved into `_apply_default_model`, which `call` (the body of
    set_default_model) calls, and which import_default_model calls too."""
    return PEMEL_PREFERENCES.replace(
        'def set_default_model(preferences: ModelPreferences, model: str, source: str):\n'
        '    preferences.default_model = model\n    preferences.default_source = source\n',
        'def _apply_default_model(preferences: ModelPreferences, model: str, source: str):\n'
        '    preferences.default_model = model\n    preferences.default_source = source\n\n\n'
        f'def set_default_model(preferences: ModelPreferences, model: str, source: str):\n{call}\n\n\n'
        'def import_default_model(preferences: ModelPreferences, model: str):\n'
        '    _apply_default_model(preferences, model, "import")\n')


def test_writes_moved_to_a_helper_called_only_under_a_condition_keep_a_line_for_each_function(tmp_path):
    """PEMEL17-18 (PEMEL Studio, 5.1 review): `if source == "library": _apply_default_model(...)` in place of
    set_default_model's own writes gave one line, `set_default_model's writes of ... moved to _apply_default_model`,
    which read as a refactor while set_default_model now wrote the fields only sometimes; PEMEL asked to keep the
    separate writer lines when the mutation moved across a condition. A call that runs whenever the function returns
    (a statement of its body or of a with block, after a guard that raises) gives one line, and its block line, with
    PEMEL's names, says what moved where; a call under an if, after an early return or in a loop gives the two 5.0.1
    lines."""
    path = 'src/pemel_service/library/model_preferences.py'
    _commit(tmp_path, {'pyproject.toml': '[project]\nname = "pemel"\nversion = "0"\n', path: PEMEL_PREFERENCES})
    moved = ("set_default_model's writes of ModelPreferences.default_model, ModelPreferences.default_source moved to "
             f'_apply_default_model, which it calls ({path}:10); other callers of _apply_default_model: '
             'import_default_model; 0 other writers, 1 reader (untyped reads not counted)')
    for call in ('    _apply_default_model(preferences, model, source)',
                 '    if not model:\n        raise ValueError("no model")\n    _apply_default_model(preferences, model, source)',
                 '    with open("log", "a"):\n        _apply_default_model(preferences, model, source)'):
        _write(tmp_path, {path: _pemel_moved(call)})
        assert [line.text for line in _impact(tmp_path)[0].lines] == [moved], call
    _write(tmp_path, {path: _pemel_moved('    _apply_default_model(preferences, model, source)')})
    code, text = _flowguard(tmp_path, 'check', '--static', '--base', 'HEAD')
    assert code == 0 and "impact: set_default_model's writes of 2 ModelPreferences fields moved to _apply_default_model, " \
        'which it calls (model_preferences.py:10); ... -> check them for this change only (python -m flowguard show ' \
        'ModelPreferences.default_model)' in text.splitlines(), text
    apart = ['_apply_default_model now writes ModelPreferences.default_model, ModelPreferences.default_source; 0 other '
             'writers, 1 reader (untyped reads not counted)',
             'set_default_model no longer writes ModelPreferences.default_model, ModelPreferences.default_source; 1 other '
             'writer, 1 reader (untyped reads not counted)']
    for call in ('    if source == "library":\n        _apply_default_model(preferences, model, source)',
                 '    if source != "library":\n        return\n    _apply_default_model(preferences, model, source)',
                 '    for _ in range(1):\n        _apply_default_model(preferences, model, source)',
                 '    try:\n        _apply_default_model(preferences, model, source)\n    finally:\n        pass',
                 '    source and _apply_default_model(preferences, model, source)'):
        _write(tmp_path, {path: _pemel_moved(call)})
        assert sorted(line.text for line in _impact(tmp_path)[0].lines) == apart, call


def test_writes_moved_into_a_helper_a_typescript_function_calls_only_on_some_paths_keep_two_lines(tmp_path):
    """PEMEL17-18 for JS/TS: the call in Planning Tool's own shape, in the `prisma.$transaction(async (tx) => ...)`
    callback where the write was, still gives one line; under an if, a ternary, `&&`, after an early return in the
    callback, in a loop or in a callback the write was not in (`forEach`), the function and the helper keep a line
    each."""
    _commit(tmp_path, {**MOVED_BASE, 'src/member-helpers.ts': '// helpers\n'})
    imports = "import { reactivateOrCreateMember } from './member-helpers';\n"
    call = 'await reactivateOrCreateMember(tx, projectId, userId);'
    _write(tmp_path, {'src/member-helpers.ts': MEMBER_HELPER, 'src/members.ts': _members_ts(call, imports)})
    [line] = _impact(tmp_path)[0].lines
    assert "assignProjectManager's writes of ProjectMember.projectId, ProjectMember.userId moved to reactivateOrCreateMember" \
        in line.text, line.text
    apart = ['assignProjectManager no longer writes ProjectMember.projectId, ProjectMember.userId; 1 other writer, 1 reader '
             'of ProjectMember',
             'reactivateOrCreateMember now writes ProjectMember.active, ProjectMember.projectId, ProjectMember.userId; 1 other '
             'writer, 1 reader of ProjectMember']
    for body in (f'if (deps.reactivate) {{\n      {call}\n    }}',
                 f'deps.reactivate ? {call[6:-1]} : null;',
                 f'deps.reactivate && {call[6:]}',
                 f'if (!deps.reactivate) return;\n    {call}',
                 f'for (const id of [userId]) {{\n      await reactivateOrCreateMember(tx, projectId, id);\n    }}',
                 '[userId].forEach((id) => reactivateOrCreateMember(tx, projectId, id));',
                 f'try {{\n      {call}\n    }} catch (error) {{\n      throw error;\n    }}'):
        _write(tmp_path, {'src/members.ts': _members_ts(body, imports)})
        assert sorted(line.text for line in _impact(tmp_path)[0].lines) == apart, body


def test_a_function_whose_update_became_a_delete_says_it_now_deletes_the_model(tmp_path):
    """PTWF-4255 (Planning Tool): `remove no longer writes Assignment.status` was right, the status update having
    become a delete, and said nothing of the delete. A delete the function had at the baseline is not new."""
    assignments = '''import { prisma } from './db';

export async function create(userId: number) {
  return prisma.assignment.create({ data: { userId, status: 'ACTIVE' } });
}

export async function remove(id: number) {
  return prisma.assignment.update({ where: { id }, data: { status: 'REMOVED' } });
}

export async function purge(id: number) {
  await prisma.assignment.update({ where: { id }, data: { status: 'GONE', userId: 0 } });
  return prisma.assignment.deleteMany({ where: { status: 'GONE' } });
}

export async function listAssignments(userId: number) {
  return prisma.assignment.findMany({ where: { userId } });
}
'''
    _commit(tmp_path, {**MOVED_BASE, 'src/assignments.ts': assignments})
    _write(tmp_path, {'src/assignments.ts': assignments.replace(
        "return prisma.assignment.update({ where: { id }, data: { status: 'REMOVED' } });",
        'return prisma.assignment.delete({ where: { id } });').replace("status: 'GONE', userId: 0", "status: 'GONE'")})
    found, modules = _impact(tmp_path)
    by_function = {line.function.rpartition(':')[2]: line for line in found.lines}
    assert by_function['remove'].text == ('remove no longer writes Assignment.status; now deletes Assignment '
                                          '(src/assignments.ts:8); 2 other writers, 1 reader of Assignment'), by_function['remove'].text
    assert 'src/assignments.ts:8' in by_function['remove'].places
    assert by_function['purge'].text == 'purge no longer writes Assignment.userId; 1 other writer, 1 reader of Assignment'


def test_a_new_read_of_a_model_no_code_creates_says_what_was_searched_and_that_it_was_read_so_at_task_start(tmp_path):
    """PTWF-V116a, PTWF-G61 (Planning Tool): a new `prisma.projectRequest.count` printed `uncreated ProjectRequest:
    registry2.ts:referenceCount reads ProjectRequest, whose rows no code creates -> fix it, or say why in your report`,
    while registry.ts:countRequests had read it so at the task start and the owner keeps the table: FlowGuard reads only
    the repository's files, and `fix it` asked for a creation path no one asked for."""
    _commit(tmp_path, MOVED_BASE)
    _write(tmp_path, {'src/registry2.ts': '''import { prisma } from './db';

export async function referenceCount(orgUnitId: number) {
  return prisma.projectRequest.count({ where: { orgUnitId } });
}
'''})
    cfg = load_config(tmp_path)
    with closing(build(tmp_path, roots=cfg.roots)) as graph:
        found = owners.static_findings(cfg, graph, anchors.collect(graph), 'HEAD')
    issue = next(issue for issue in found.issues if issue.name == 'uncreated:ProjectRequest')
    assert issue.text == ('Rows of ProjectRequest: read src/registry.ts:4  src/registry2.ts:4; no create/upsert/INSERT of '
                          'ProjectRequest found in the files FlowGuard reads'), issue.text
    step = ('find where these rows come from (seeds, migrations, another system) and say so in your report; python -m '
            'flowguard known add uncreated:ProjectRequest --act leave --why TEXT records a creator outside the repository')
    lines, _ = signals.deliver(found.issues, touched_functions=found.touched_functions, touched_files=found.touched_files,
                               ran=found.ran, extra=found.lines)
    [line] = [line for line in lines if line.name == 'uncreated:ProjectRequest']
    assert (line.kind, line.text, line.step) == (
        'impact', 'uncreated ProjectRequest: src/registry2.ts:referenceCount reads ProjectRequest; no creator found; '
        'ProjectRequest was already read so at task start (src/registry.ts:countRequests)', step), line
    # A model no code used at the task start has no such clause; the line is impact, the old reader's before.
    code, text = _flowguard(tmp_path, 'check', '--static', '--all', '--base', 'HEAD')
    assert code == 0 and ('before: uncreated ProjectRequest at registry.ts:countRequests was broken at task start -> '
                          'leave it unless your task is about it') in text, text
    assert f'-> {step}' in text and 'fix it, or say why' not in text, text
    _commit(tmp_path, message='registry2')
    _write(tmp_path, {'src/assign.ts': '''import { prisma } from './db';

export async function listAll() {
  return prisma.assignment.findMany({ where: { status: 'ACTIVE' } });
}
'''})
    cfg = load_config(tmp_path)
    with closing(build(tmp_path, roots=cfg.roots)) as graph:
        found = owners.static_findings(cfg, graph, anchors.collect(graph), 'HEAD')
    lines, _ = signals.deliver(found.issues, touched_functions=found.touched_functions, touched_files=found.touched_files,
                               ran=found.ran, extra=found.lines)
    assert [(line.kind, line.text) for line in lines if line.name.startswith('uncreated:')] == [
        ('impact', 'uncreated Assignment: src/assign.ts:listAll reads Assignment; no creator found')], lines
