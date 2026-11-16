"""Documents tied to code (design 4.4; R91, R92): a Markdown text marked `<!-- flowguard: about SITE -->` is named
in the block when a change edits that site and leaves the text as it was, never red; a marker this change writes
with a site that names nothing is red; a known.toml site may be a whole document.

Planning Tool's docs had 40 of 91 checkable claims out of date: they were true once, and nobody was told when the
code they describe changed.
"""
from tests.intent_engine.test_static_check import _block, _commit, _static, _write

# The block shortens a path to its file name when no other file of the repository has that name.

CODE = '''export function rate(x: number) { return x * 2; }
export function other(x: number) { return x + 1; }
'''
DOC = '''# Rates

<!-- flowguard: about app/a.ts:rate -->
The rate doubles the input.

## Other

Nothing here describes code.
'''
LINE = ('impact: rates.md:3 describes app/a.ts:rate, which this change edits -> '
        'reread that text and correct it if it no longer holds')


def _said(root):
    code, text = _static(root)
    return code, [line for line in _block(text) if 'rates.md' in line or 'about ' in line], text


def test_a_change_to_the_described_code_names_the_text_and_never_fails(tmp_path):
    _commit(tmp_path, {'app/a.ts': CODE, 'docs/rates.md': DOC})
    _write(tmp_path, {'app/a.ts': CODE.replace('x * 2', 'x * 3')})
    code, lines, text = _said(tmp_path)
    assert code == 0 and lines == [LINE], text
    # The same change that corrects the text has nothing left to say.
    _write(tmp_path, {'docs/rates.md': DOC.replace('doubles', 'triples')})
    code, lines, text = _said(tmp_path)
    assert code == 0 and lines == [], text
    # Another function of the same file is not the site; a comment inside the site is an edit of it.
    _write(tmp_path, {'docs/rates.md': DOC, 'app/a.ts': CODE.replace('x + 1', 'x + 2')})
    assert _said(tmp_path)[1] == []
    _write(tmp_path, {'app/a.ts': CODE.replace('{ return x * 2; }', '{ /* times two */ return x * 2; }')})
    assert _said(tmp_path)[1] == [LINE]


def test_a_heading_after_the_marker_ties_its_whole_section_and_a_file_site_its_whole_file(tmp_path):
    doc = '''# Service

<!-- flowguard: about app/a.ts -->
## The rates file

Both functions live here.

### Details

Still the same section.

## Next

Not tied.
'''
    _commit(tmp_path, {'app/a.ts': CODE, 'docs/rates.md': doc})
    _write(tmp_path, {'app/a.ts': CODE.replace('x + 1', 'x + 2')})
    code, lines, text = _said(tmp_path)
    assert code == 0 and lines == ['impact: rates.md:3 describes app/a.ts, which this change edits -> '
                                   'reread that text and correct it if it no longer holds'], text
    # An edit of the section's own subheading text corrects it; one under the next heading of its level does not.
    _write(tmp_path, {'docs/rates.md': doc.replace('Still the same section.', 'Updated.')})
    assert _said(tmp_path)[1] == []
    _write(tmp_path, {'docs/rates.md': doc.replace('Not tied.', 'Also not tied.')})
    assert len(_said(tmp_path)[1]) == 1


def test_a_new_marker_that_names_nothing_is_red_and_an_old_one_whose_code_this_change_removed_is_named(tmp_path):
    _commit(tmp_path, {'app/a.ts': CODE, 'docs/rates.md': DOC})
    _write(tmp_path, {'docs/rates.md': DOC + '\n<!-- flowguard: about app/a.ts:missing -->\nGone.\n'})
    code, lines, text = _said(tmp_path)
    assert code == 1 and len(lines) == 1 and lines[0].startswith('red: about app/a.ts:missing: site app/a.ts:missing names nothing'), text
    _write(tmp_path, {'docs/rates.md': DOC, 'app/a.ts': 'export function other(x: number) { return x + 1; }\n'})
    code, lines, text = _said(tmp_path)
    assert code == 0 and lines == ['impact: rates.md:3 describes app/a.ts:rate, which names nothing now -> '
                                   'update that text and its marker, or remove them'], text


def test_a_marker_written_as_code_is_text_not_a_marker(tmp_path):
    # FlowGuard's own guide shows the syntax in code spans; 4.4 read them as markers and its own run was red.
    guide = '''# Markers

Put `<!-- flowguard: about path:symbol -->` above a text; a list goes between
``<!-- flowguard: generate KIND ARG -->`` and `<!-- flowguard: end -->`.

```markdown
<!-- flowguard: about app/a.ts:missing -->
## Not a heading either
<!-- flowguard: generate fields Missing -->
```

~~~
<!-- flowguard: about app/gone.ts -->
~~~
'''
    _commit(tmp_path, {'app/a.ts': CODE, 'docs/rates.md': DOC})
    _write(tmp_path, {'docs/guide.md': guide, 'app/a.ts': CODE.replace('x * 2', 'x * 3')})
    code, text = _static(tmp_path)
    assert code == 0 and [line for line in _block(text) if 'guide.md' in line or 'about ' in line] == [], text
    from flowguard.intent.docs import markers, regions
    assert markers(guide) == [] and regions(guide) == []
    # A real marker after a closed fence counts, and a `#` line inside a fence does not end its heading's section.
    after = guide + '\n<!-- flowguard: about app/a.ts:rate -->\n## Rate\n\n```sh\n# a comment\n```\nStill the rate.\n\n## Next\n'
    assert markers(after) == [('app/a.ts:rate', 16, '## Rate\n\n```sh\n# a comment\n```\nStill the rate.')]


def test_a_known_entry_may_name_a_whole_document(tmp_path):
    # Planning Tool's team instructions point to files that are gone (K8): the entry names the document itself.
    known = ('[known.stale-pointers]\nsites = ["docs/rates.md"]\nwhy = "It points to files that are gone"\n'
             'act = "ask"\nask = "Should the pointers be removed?"\n')
    _commit(tmp_path, {'app/a.ts': CODE, 'docs/rates.md': DOC, '.flowguard/known.toml': known})
    _write(tmp_path, {'docs/rates.md': DOC.replace('Nothing here', 'Nothing yet')})
    code, text = _static(tmp_path)
    assert code == 0 and any(line.startswith('known: known.stale-pointers at rates.md -> an open question for the owner') for line in _block(text)), text
    # A document site that is not there is an invalid entry, red.
    _write(tmp_path, {'.flowguard/known.toml': known.replace('docs/rates.md', 'docs/gone.md')})
    code, text = _static(tmp_path)
    assert code == 1 and any(line.startswith('red: known.stale-pointers:') for line in _block(text)), text


SCHEMA = 'model Job {\n  id    String  @id\n  share Decimal @map("job_share")\n  state String?\n}\n'
SOURCE = '''export const MAX_SHARE = 2;
export const JobKind = { A: 'A', B: 'B' } as const;
export function shareLimit(kind: string): number { return kind === JobKind.A ? MAX_SHARE : 1; }
export function label(job: { id: string }) { return job.id; }
'''
REGIONS = '''# Jobs

<!-- flowguard: generate fields Job -->
<!-- flowguard: end -->

<!-- flowguard: generate values JobKind -->
<!-- flowguard: end -->

<!-- flowguard: generate functions app/jobs.ts -->
<!-- flowguard: end -->

<!-- flowguard: generate constants app/jobs.ts -->
<!-- flowguard: end -->
'''


def test_generated_regions_are_written_from_the_map_and_named_when_out_of_date(tmp_path):
    from tests.intent_engine.test_static_check import _flowguard
    _commit(tmp_path, {'prisma/schema.prisma': SCHEMA, 'prisma/schema.sqlite.prisma': SCHEMA.replace('String?', 'Int?'),
                       'app/jobs.ts': SOURCE, 'docs/jobs.md': '# Jobs\n'})
    _write(tmp_path, {'docs/jobs.md': REGIONS + '\nMore text.\n'})       # this change writes the four regions
    code, text = _static(tmp_path)
    from tests.intent_engine._cli_fixture import last
    assert code == 0 and [line for line in last(tmp_path).splitlines() if 'jobs.md' in line] == [
        f'impact: docs/jobs.md:{line} generate {what} is out of date -> python -m flowguard docs rewrites it' for line, what in
        [(3, 'fields Job'), (6, 'values JobKind'), (9, 'functions app/jobs.ts'), (12, 'constants app/jobs.ts')]], text
    code, out = _flowguard(tmp_path, 'docs')
    assert code == 0 and out.splitlines() == [f'docs/jobs.md:{line} generate {what}: rewritten' for line, what in
                                              [(3, 'fields Job'), (6, 'values JobKind'), (9, 'functions app/jobs.ts'), (12, 'constants app/jobs.ts')]], out
    written = (tmp_path / 'docs/jobs.md').read_text(encoding='utf-8')
    assert written == '''# Jobs

<!-- flowguard: generate fields Job -->
| Field | Type | Column |
|---|---|---|
| id | String | id |
| share | Decimal | job_share |
| state | String? (prisma/schema.prisma), Int? (prisma/schema.sqlite.prisma) | state |
<!-- flowguard: end -->

<!-- flowguard: generate values JobKind -->
- `A`
- `B`
<!-- flowguard: end -->

<!-- flowguard: generate functions app/jobs.ts -->
| Function | Signature |
|---|---|
| `shareLimit` | `function shareLimit(kind: string): number` |
| `label` | `function label(job: { id: string })` |
<!-- flowguard: end -->

<!-- flowguard: generate constants app/jobs.ts -->
| Constant | Value |
|---|---|
| `MAX_SHARE` | `2` |
<!-- flowguard: end -->

More text.
''', written
    assert [line for line in _block(_static(tmp_path)[1]) if 'jobs.md' in line] == []
    assert _flowguard(tmp_path, 'docs')[1].splitlines() == ['no generated region is out of date']
    # A change to the code dates the region it is written from, and only that one.
    _commit(tmp_path, message='regions written')
    assert _flowguard(tmp_path, 'new-task')[0] == 0
    _write(tmp_path, {'app/jobs.ts': SOURCE.replace('MAX_SHARE = 2', 'MAX_SHARE = 3')})
    assert [line for line in _block(_static(tmp_path)[1]) if 'jobs.md' in line] == [
        'impact: jobs.md:23 generate constants app/jobs.ts is out of date -> python -m flowguard docs rewrites it']


# Planning Tool's documents (T5, R99): long texts with generated regions of a constants file, a Prisma model and a
# value set, committed before the code they list moved on.
PT_COLORS = """/** 0 - 30 %: critically under-utilised (red). */
export const UTILIZATION_THRESHOLD_LOW = 30;

/** 30 - 90 %: partially utilised / warning (yellow). */
export const UTILIZATION_THRESHOLD_MID = 90;

/** Reserved red for capacity and 100% reference lines. */
export const CAPACITY_LINE_COLOR = '#b9052d';
"""
PT_SCHEMA = """model Customer {
  id        String   @id @default(uuid())
  name      String
  createdAt DateTime @default(now()) @map("created_at")

  @@map("customers")
}

model Project {
  id         String @id @default(uuid())
  customerId String @map("customer_id")
}
"""
PT_GRANULARITY = "export const GRANULARITIES = ['DAY', 'WEEK', 'MONTH'] as const;\n"
PT_DOC = """# Frontend Documentation

## 1. Technology Stack

React, TanStack Query, vitest.

## Utilization thresholds

<!-- flowguard: generate constants frontend/src/constants/utilization-colors.ts -->
| Constant | Value |
|---|---|
| `UTILIZATION_THRESHOLD_LOW` | `25` |
<!-- flowguard: end -->

## Customer fields

<!-- flowguard: generate fields Customer -->
<!-- flowguard: end -->

## Granularities

<!-- flowguard: generate values GRANULARITIES -->
- `DAY`
<!-- flowguard: end -->
"""


def test_a_stale_region_is_named_only_when_this_change_edits_its_source_or_the_region_and_the_brief_counts_them(tmp_path):
    """R99: a run does not push old problems on every task. Regions an earlier change left out of date say nothing in
    the block until this change edits a file they are written from or the region itself; the session brief counts
    them on one line, and check --all lists each."""
    from tests.intent_engine.test_static_check import _flowguard
    colors, schema, granularity = ('frontend/src/constants/utilization-colors.ts', 'backend/prisma/schema.prisma',
                                   'frontend/src/constants/granularity.ts')
    _commit(tmp_path, {colors: PT_COLORS, schema: PT_SCHEMA, granularity: PT_GRANULARITY,
                       'frontend/src/utils/sap-reference.ts': 'export const MAX_SAP_REFERENCE = 2_147_483_647;\n',
                       'docs/FRONTEND_DOCUMENTATION.md': PT_DOC})
    lines = [index + 1 for index, line in enumerate(PT_DOC.splitlines()) if 'flowguard: generate' in line]
    constants, fields, values = (f'impact: FRONTEND_DOCUMENTATION.md:{line} generate {what} is out of date -> '
                                 'python -m flowguard docs rewrites it' for line, what in
                                 zip(lines, [f'constants {colors}', 'fields Customer', 'values GRANULARITIES']))
    count = '3 generated regions are out of date: python -m flowguard docs rewrites them'
    def said(*options):
        code, text = _static(tmp_path, *options)
        assert code == 0, text
        return [line for line in _block(text, everything=bool(options)) if 'generate ' in line]
    def brief():
        code, text = _flowguard(tmp_path)
        assert code == 0, text
        return [line for line in text.splitlines() if 'generated region' in line]
    assert said() == [] and brief() == [count]            # no change: nothing in the block, one count in the brief
    _write(tmp_path, {'frontend/src/utils/sap-reference.ts': 'export const MAX_SAP_REFERENCE = 2_147_483_646;\n'})
    assert said() == [] and brief() == [count]            # an unrelated edit
    _write(tmp_path, {'frontend/src/utils/sap-reference.ts': 'export const MAX_SAP_REFERENCE = 2_147_483_647;\n',
                      colors: PT_COLORS.replace('= 30;', '= 31;')})
    assert said() == [constants]                          # the file a constants region lists
    _write(tmp_path, {colors: PT_COLORS, schema: PT_SCHEMA.replace('customerId String', 'customerId String?')})
    assert said() == [fields]                             # a Prisma schema, which a fields region reads all of
    _write(tmp_path, {schema: PT_SCHEMA, granularity: PT_GRANULARITY.replace("'MONTH'", "'MONTH', 'YEAR'")})
    assert said() == [values]                             # the file that declares the value set
    _write(tmp_path, {granularity: PT_GRANULARITY,
                      'docs/FRONTEND_DOCUMENTATION.md': PT_DOC.replace('`25`', '`26`').replace('React,', 'React 18,')})
    assert said() == [constants]                          # an edit inside a region, not one outside them
    _write(tmp_path, {'docs/FRONTEND_DOCUMENTATION.md': PT_DOC})
    assert said('--all') == [constants, fields, values]   # --all lists every one
    code, out = _flowguard(tmp_path, 'docs')
    assert code == 0 and len(out.splitlines()) == 3, out
    assert said() == [] and brief() == []                 # rewritten: none is out of date


def test_a_constants_region_lists_a_module_constant_that_is_an_array_of_literals(tmp_path):
    """T4 (U2.5): the JS/TS reader now keeps a module-level array of literals (`[0, 5, 50] as const`) as the constant's
    value, so `generate constants` lists it beside the scalar constants, which it lists as before; an array with a
    spread and a function's own array are no module-level literal constant."""
    from tests.intent_engine.test_static_check import _flowguard
    source = ("export const MAX_SHARE = 2;\nexport const PROBABILITY_STEPS = [0, 5, 50, 75, 90, 100] as const;\n"
              "const MONTHS = ['Jan', 'Feb'];\nconst MORE = [...MONTHS, 'Mar'];\n"
              "export function steps() { const LOCAL = [1, 2]; return LOCAL.length + MORE.length; }\n")
    region = '<!-- flowguard: generate constants app/steps.ts -->\n<!-- flowguard: end -->\n'
    _commit(tmp_path, {'app/steps.ts': source, 'docs/steps.md': '# Steps\n\n' + region})
    code, out = _flowguard(tmp_path, 'docs')
    assert code == 0 and out.splitlines() == ['docs/steps.md:3 generate constants app/steps.ts: rewritten'], out
    assert (tmp_path / 'docs/steps.md').read_text(encoding='utf-8') == """# Steps

<!-- flowguard: generate constants app/steps.ts -->
| Constant | Value |
|---|---|
| `MAX_SHARE` | `2` |
| `PROBABILITY_STEPS` | `[0, 5, 50, 75, 90, 100]` |
| `MONTHS` | `["Jan", "Feb"]` |
<!-- flowguard: end -->
"""


def test_a_region_this_change_writes_that_cannot_be_generated_is_red(tmp_path):
    _commit(tmp_path, {'prisma/schema.prisma': SCHEMA, 'app/jobs.ts': SOURCE, 'docs/jobs.md': '# Jobs\n'})
    _write(tmp_path, {'docs/jobs.md': '# Jobs\n\n<!-- flowguard: generate fields Missing -->\n<!-- flowguard: end -->\n\n'
                                      '<!-- flowguard: generate routes app -->\n<!-- flowguard: end -->\n\n'
                                      '<!-- flowguard: generate values JobKind -->\nno end\n'})
    code, text = _static(tmp_path)
    reds = [line for line in _block(text) if line.startswith('red:')]
    assert code == 1 and reds == [
        'red: generate fields Missing: generate fields Missing: no Prisma model Missing -> correct the marker at jobs.md:3',
        'red: generate routes app: generate routes: the kinds are fields, values, functions, constants -> correct the marker at jobs.md:6',
        'red: generate values JobKind: generate values JobKind has no <!-- flowguard: end --> marker -> correct the marker at jobs.md:9'], text


def test_a_values_region_reads_the_sets_show_lists_and_leaves_out_what_only_tests_or_unused_schemas_declare(tmp_path):
    """Planning Tool (5.0 review, entry:F4): `show OrgUnitTab` listed the one production set, while `generate values
    OrgUnitTab` also read the e2e helper's redeclaration (frontend/tests/e2e/local-azure/support/nav.ts) and could not be
    written (`2 different value sets have that name`), a red no marker fixes; `generate values ADMIN_ACTORS` wrote a
    test file's members as the project's. The region now reads the sets the values lines of `show NAME` give
    (`owners.value_sets_named`): what only test files declare is left out, and the enum of a Prisma schema not in use,
    which show lists as such, is not written; a Prisma enum of a schema in use is written under its own name."""
    from tests.intent_engine.test_static_check import _flowguard
    in_use = ('datasource db {\n  provider = "postgresql"\n  url      = env("DATABASE_URL")\n}\n\n'
              'enum JobState {\n  QUEUED\n  DONE\n}\n\nmodel Job {\n  id    String   @id\n  state JobState\n}\n')
    template = ('datasource db {\n  provider = "sqlite"\n  url      = "file:./dev.db"\n}\n\n'
                'enum AppRole {\n  SYSTEM_ADMIN\n  EMPLOYEE\n}\n\nenum AssignmentStatus {\n  DRAFT\n  ACTIVE\n}\n')
    regions = ''.join(f'<!-- flowguard: generate values {name} -->\n<!-- flowguard: end -->\n\n'
                      for name in ('OrgUnitTab', 'ADMIN_ACTORS', 'AppRole', 'JobState', 'AssignmentStatus'))
    _commit(tmp_path, {
        'frontend/src/utils/org-unit-tab.ts': "export type OrgUnitTab = 'overview' | 'absences' | 'planning';\n",
        'frontend/tests/e2e/local-azure/support/nav.ts': ("export type OrgUnitTab = 'Overview' | 'Absences';\n"
                                                          "export function orgUnitTab(tab: OrgUnitTab) { return tab; }\n"),
        'frontend/tests/unit/fg-org-unit-delete-authority.decision-table.test.ts':
            "const ADMIN_ACTORS = ['SYSTEM_ADMIN', 'PLANNING_ADMIN'] as const;\nexport const actors = ADMIN_ACTORS;\n",
        'backend/src/types/prisma-enums.ts': "export type AppRole = 'DEVELOPER' | 'SYSTEM_ADMIN' | 'EMPLOYEE';\n",
        'backend/prisma/schema.prisma': in_use,
        'backend/prisma/schema.sqlite.prisma': template,
        'docs/FUNCTION_INVENTORY.md': '# Functions\n',
    })
    _write(tmp_path, {'docs/FUNCTION_INVENTORY.md': '# Functions\n\n' + regions})
    code, out = _flowguard(tmp_path, 'docs')
    assert code == 1 and out.splitlines() == [
        'docs/FUNCTION_INVENTORY.md:3 generate values OrgUnitTab: rewritten',
        'docs/FUNCTION_INVENTORY.md:6 generate values ADMIN_ACTORS: generate values ADMIN_ACTORS: no value set of that name',
        'docs/FUNCTION_INVENTORY.md:9 generate values AppRole: rewritten',
        'docs/FUNCTION_INVENTORY.md:12 generate values JobState: rewritten',
        'docs/FUNCTION_INVENTORY.md:15 generate values AssignmentStatus: generate values AssignmentStatus: only the enum of a Prisma '
        'schema not in use has that name (enum AssignmentStatus backend/prisma/schema.sqlite.prisma:11, a schema not in use)'], out
    written = (tmp_path / 'docs/FUNCTION_INVENTORY.md').read_text(encoding='utf-8')
    assert '- `overview`\n- `absences`\n- `planning`\n' in written and '`Overview`' not in written, written
    assert '- `DEVELOPER`\n- `SYSTEM_ADMIN`\n- `EMPLOYEE`\n' in written and '- `QUEUED`\n- `DONE`\n' in written, written
    assert '`PLANNING_ADMIN`' not in written, written
    # show lists what the regions read, the template's enum marked as such
    def values(name):
        code, text = _flowguard(tmp_path, 'show', name)
        assert code == 0, text
        return [line for line in text.splitlines() if line.startswith('values ')]
    assert values('OrgUnitTab') == ['values OrgUnitTab: overview | absences | planning (frontend/src/utils/org-unit-tab.ts:1)']
    assert values('ADMIN_ACTORS') == []
    assert values('AppRole') == ['values AppRole: DEVELOPER | SYSTEM_ADMIN | EMPLOYEE (backend/src/types/prisma-enums.ts:1)',
                                 'values AppRole: SYSTEM_ADMIN | EMPLOYEE (enum AppRole backend/prisma/schema.sqlite.prisma:6, a schema not in use)']
    # a region newly written for the production set is no red; the two that name no set are
    _write(tmp_path, {'docs/FUNCTION_INVENTORY.md': written.replace(
        '<!-- flowguard: generate values ADMIN_ACTORS -->\n<!-- flowguard: end -->\n\n', '').replace(
        '<!-- flowguard: generate values AssignmentStatus -->\n<!-- flowguard: end -->\n\n', '')})
    code, text = _static(tmp_path)
    assert code == 0 and [line for line in _block(text) if line.startswith('red:')] == [], text


# ---- module contracts and their connections (R98) ---------------------------------------------------------------
# The owner: hang what AI found on the code; a module's contract says what it connects to, and a change reminds the
# agent of the connected places. A text about a file or folder is that module's contract.

CALLER = '''import { rate } from './a';
export function charge(x: number) { return rate(x) + 1; }
'''
CONTRACT = '''# Billing

<!-- flowguard: about app/b.ts -->
Billing charges the rate plus one.
'''


def test_a_change_names_the_contracts_of_the_modules_its_edited_functions_connect_to(tmp_path):
    from tests.intent_engine.test_static_check import _flowguard
    _commit(tmp_path, {'app/a.ts': CODE, 'app/b.ts': CALLER, 'docs/billing.md': CONTRACT})
    _write(tmp_path, {'app/a.ts': CODE.replace('x * 2', 'x * 3')})
    code, text = _static(tmp_path)
    lines = [line for line in _block(text) if 'billing.md' in line]
    assert code == 0 and lines == ['impact: billing.md:3 describes app/b.ts, whose app/b.ts:charge calls app/a.ts:rate, '
                                   'which this change edits -> reread that text and correct it if it no longer holds'], text
    # A function nobody else calls connects to nothing; a change that also corrects the contract has nothing to say.
    _write(tmp_path, {'app/a.ts': CODE.replace('x + 1', 'x + 2')})
    assert [line for line in _block(_static(tmp_path)[1]) if 'billing.md' in line] == []
    _write(tmp_path, {'app/a.ts': CODE.replace('x * 2', 'x * 3'),
                      'docs/billing.md': CONTRACT.replace('the rate plus one', 'three times plus one')})
    assert [line for line in _block(_static(tmp_path)[1]) if 'billing.md' in line] == []
    # show PATH prints a module's contracts and connections, with theirs.
    _write(tmp_path, {'app/a.ts': CODE, 'docs/billing.md': CONTRACT})
    code, out = _flowguard(tmp_path, 'show', 'app/b.ts')
    assert code == 0 and out.splitlines() == ['module app/b.ts: 1 file, 1 function', 'described by docs/billing.md:3',
                                              'calls app/a.ts (1 call)'], out
    code, out = _flowguard(tmp_path, 'show', 'app/a.ts')
    assert code == 0 and out.splitlines() == [
        'module app/a.ts: 1 file, 2 functions',
        'described by no text: put <!-- flowguard: about app/a.ts --> above the Markdown text that is its contract',
        'called by app/b.ts (1 call; described by docs/billing.md:3)'], out


def test_a_folder_is_a_module_and_a_folder_with_no_mapped_file_is_red(tmp_path):
    from tests.intent_engine.test_static_check import _flowguard
    folder = '# App\n\n<!-- flowguard: about app/ -->\nThe app folder holds the rates and billing.\n'
    _commit(tmp_path, {'app/a.ts': CODE, 'app/b.ts': CALLER, 'docs/app.md': folder})
    _write(tmp_path, {'app/b.ts': CALLER.replace('+ 1', '+ 2')})
    code, text = _static(tmp_path)
    assert code == 0 and [line for line in _block(text) if 'app.md' in line] == [
        'impact: app.md:3 describes app/, which this change edits -> reread that text and correct it if it no longer holds'], text
    code, out = _flowguard(tmp_path, 'show', 'app')
    assert code == 0 and out.splitlines()[:2] == ['module app/: 2 files, 3 functions', 'described by docs/app.md:3'], out
    _write(tmp_path, {'app/b.ts': CALLER, 'docs/app.md': folder + '\n<!-- flowguard: about lib/ -->\nGone.\n'})
    code, text = _static(tmp_path)
    assert code == 1 and any(line.startswith('red: about lib/: site lib/: no mapped file in this folder') for line in _block(text)), text


PT_ALLOCATION = '''export const allocationService = {
  async get(id: string) {
    return { id };
  },
};
'''
PT_COVERAGE = '''export function allocatedFteInPeriod(rows: { day: Date; fte: number }[]): number {
  const days = new Map<number, number>();
  for (const row of rows) {
    days.set(row.day.getTime(), (days.get(row.day.getTime()) ?? 0) + row.fte);
  }
  const first = rows.find((row) => row.fte > 0);
  return first ? first.fte : 0;
}
'''
PT_CAPACITY = '''import { allocatedFteInPeriod } from '../utils/allocation-coverage';
export function capacityOf(rows: { day: Date; fte: number }[]) { return 1 - allocatedFteInPeriod(rows); }
'''
PT_DIALOG = '''export function buildSyncEntries(entries: { id: string; open: boolean }[]) {
  return entries.find((entry) => entry.open);
}
'''
PT_NETLOG = '''class NetLog {
  lines: string[] = [];
  find(text: string) {
    return this.lines.filter((line) => line.includes(text));
  }
}
export const log = new NetLog();
'''


def test_a_module_connects_only_through_the_calls_the_map_resolved(tmp_path):
    """Planning Tool (5.0 review, pt:F7): `show backend/src/utils/` said `calls backend/src/services/allocation.service.ts
    (6 calls)`, which were `days.get(...)` and `groups.get(...)` on Maps matched by the name `get` alone to
    allocationService.get, and 43 frontend components `called` the e2e helper NetLog.find through ordinary Array.find
    calls. The module view and the contracts a change names (`_linked`) count only the calls the map resolved."""
    from tests.intent_engine.test_static_check import _flowguard
    contract = '# Utilities\n\n<!-- flowguard: about backend/src/utils/ -->\nThe utilities compute allocation coverage.\n'
    _commit(tmp_path, {'backend/package.json': '{"name": "backend"}\n', 'frontend/package.json': '{"name": "frontend"}\n',
                       'backend/src/services/allocation.service.ts': PT_ALLOCATION,
                       'backend/src/utils/allocation-coverage.ts': PT_COVERAGE,
                       'backend/src/services/capacity.service.ts': PT_CAPACITY,
                       'frontend/src/components/AbsenceSyncDialog.tsx': PT_DIALOG,
                       'frontend/tests/e2e/local-azure/m117-add-project-from-details.live.spec.ts': PT_NETLOG,
                       'docs/utils.md': contract})
    def show(path):
        code, out = _flowguard(tmp_path, 'show', path)
        assert code == 0, out
        return out.splitlines()
    assert show('backend/src/utils/') == [
        'module backend/src/utils/: 1 file, 1 function', 'described by docs/utils.md:3',
        'called by backend/src/services/capacity.service.ts (1 call)']
    assert show('frontend/src/components/AbsenceSyncDialog.tsx') == [
        'module frontend/src/components/AbsenceSyncDialog.tsx: 1 file, 1 function',
        'described by no text: put <!-- flowguard: about frontend/src/components/AbsenceSyncDialog.tsx --> above the '
        'Markdown text that is its contract']
    # An edit of allocationService.get connects to no utility; one of the resolved caller names the contract.
    def named():
        code, text = _static(tmp_path)
        assert code == 0, text
        return [line for line in _block(text) if 'utils.md' in line]
    _write(tmp_path, {'backend/src/services/allocation.service.ts': PT_ALLOCATION.replace('{ id }', '{ id, found: true }')})
    assert named() == []
    _write(tmp_path, {'backend/src/services/allocation.service.ts': PT_ALLOCATION,
                      'backend/src/services/capacity.service.ts': PT_CAPACITY.replace('1 - ', '2 - ')})
    said = named()         # the block cuts the middle of the line: it is 214 characters long
    assert len(said) == 1 and said[0].startswith('impact: utils.md:3 describes backend/src/utils/, whose backend/src/utils/') \
        and said[0].endswith('capacity.service.ts:capacityOf, which this change edits -> reread that text and correct it '
                             'if it no longer holds'), said


PT_SQL_SCHEMA = '''datasource db {
  provider = "sqlserver"
  url      = env("DATABASE_URL")
}

model Assignment {
  id     String @id
  status String @default("DRAFT")

  @@map("assignments")
}
'''
PT_CHECK = '''CREATE TABLE assignments (
  id NVARCHAR(36) PRIMARY KEY,
  status NVARCHAR(20) NOT NULL DEFAULT 'DRAFT',
  CONSTRAINT ck_assignments_status CHECK (status IN ('DRAFT', 'ACTIVE', 'CLOSED', 'CANCELED', 'REMOVED'))
);
'''
PT_HEALTH = '''export function healthBody(database: boolean): string {
  const overallStatus = database ? 'healthy' : 'degraded';
  return JSON.stringify({ status: overallStatus });
}
'''
PT_ALERT = '''/**
 * Alert component for status messages.
 */
export function Alert(props: { text: string }) {
  return <div role="status">{props.text}</div>;
}
'''
PT_WEEK = '''import { GRANULARITIES } from '../constants/granularity';
export function weekly(): boolean { return GRANULARITIES.includes('WEEK'); }
'''
PT_MONTH = '''const GRANULARITIES = ['DAY', 'WEEK', 'MONTH', 'YEAR'] as const;
export function monthly(): number { return GRANULARITIES.length; }
'''
PT_DATA = '''# Data

<!-- flowguard: generate values Assignment.status -->
- `DRAFT`
- `ACTIVE`
<!-- flowguard: end -->

<!-- flowguard: generate values GRANULARITIES -->
- `DAY`
<!-- flowguard: end -->
'''


def test_an_old_values_region_is_named_by_a_file_that_declares_its_set_then_or_now_never_by_its_name_alone(tmp_path):
    """Planning Tool (5.0 review, code:F2, entry:F2, TD9): a stale `generate values Assignment.status` region was named
    by an edit of any file whose baseline text held the word `status`, 153 of PT's 466 frontend and backend sources
    (backend/src/api/routes/health.routes.ts with `{ status: overallStatus }`, frontend/src/components/ui/Alert.tsx with
    `status` in a comment and `role="status"`); a `GRANULARITIES` region by a file that only imports the set. A region is
    named when this change edits a file whose map facts declare the set at the baseline or now: the SQL CHECK, the file
    that held the declaration this change removes. One that cannot be written (two different sets) is an old matter
    too (R99), and the brief counts both kinds; `python -m flowguard docs` leaves the count right (entry:F3)."""
    from tests.intent_engine.test_static_check import _flowguard
    schema, check, health, alert, granularity, week, month = (
        'backend/prisma/schema.prisma', 'backend/prisma/azure-sql-setup.sql', 'backend/src/api/routes/health.routes.ts',
        'frontend/src/components/ui/Alert.tsx', 'frontend/src/constants/granularity.ts', 'frontend/src/views/week.ts',
        'frontend/src/views/month.ts')
    files = {'backend/package.json': '{"name": "backend"}\n', 'frontend/package.json': '{"name": "frontend"}\n',
             schema: PT_SQL_SCHEMA, check: PT_CHECK, health: PT_HEALTH, alert: PT_ALERT, granularity: PT_GRANULARITY,
             week: PT_WEEK, month: PT_MONTH, 'docs/data.md': PT_DATA}
    _commit(tmp_path, files)
    status, granularities = (f'impact: data.md:{line} generate values {name} {what}' for line, name, what in (
        (3, 'Assignment.status', 'is out of date -> python -m flowguard docs rewrites it'),
        (8, 'GRANULARITIES', 'cannot be written -> correct its marker or remove the region')))
    def said(*options):
        code, text = _static(tmp_path, *options)
        assert code == 0, text
        return [line for line in _block(text, everything=bool(options)) if 'generate ' in line]
    def brief(*arguments):
        code, text = _flowguard(tmp_path, *arguments)
        assert code == 0, text
        return [line for line in text.splitlines() if 'generated region' in line]
    assert said() == []
    assert brief() == ['2 generated regions are out of date, 1 of them cannot be written: '
                       'python -m flowguard docs rewrites the others and says why']
    # Files that hold the set's or the field's name and declare no set say nothing.
    for path, old, new in ((health, "'degraded'", "'impaired'"), (alert, '{props.text}', '{props.text.trim()}'),
                           (week, "'WEEK'", "'MONTH'")):
        _write(tmp_path, {path: files[path].replace(old, new)})
        assert said() == [], path
        _write(tmp_path, {path: files[path]})
    # The CHECK declares Assignment.status, month.ts one of the two GRANULARITIES.
    _write(tmp_path, {check: PT_CHECK.replace(", 'REMOVED'", '')})
    assert said() == [status]
    _write(tmp_path, {check: PT_CHECK, month: PT_MONTH.replace("'YEAR'", "'QUARTER'")})
    assert said() == [granularities]
    # granularity.ts declared the set at the baseline: the change that removes it leaves month.ts's set alone.
    _write(tmp_path, {month: PT_MONTH, granularity: 'export const UNIT = 1;\n'})
    assert said() == [granularities.replace('cannot be written -> correct its marker or remove the region',
                                            'is out of date -> python -m flowguard docs rewrites it')]
    # The Prisma field is what makes the CHECK's column Assignment.status: removing it names the region.
    _write(tmp_path, {granularity: PT_GRANULARITY, schema: PT_SQL_SCHEMA.replace('  status String @default("DRAFT")\n', '')})
    assert said() == [status.replace('is out of date -> python -m flowguard docs rewrites it',
                                     'cannot be written -> correct its marker or remove the region')]
    _write(tmp_path, {schema: PT_SQL_SCHEMA})
    assert said('--all') == [status, granularities]
    # docs rewrites what it can; the brief and new-task count what is left, without a check in between.
    code, out = _flowguard(tmp_path, 'docs')
    assert code == 1 and out.splitlines() == [
        'docs/data.md:3 generate values Assignment.status: rewritten',
        'docs/data.md:8 generate values GRANULARITIES: generate values GRANULARITIES: 2 different value sets have that name'], out
    assert brief() == ['1 generated region cannot be written: python -m flowguard docs says why']
    assert brief('new-task') == ['1 generated region cannot be written: python -m flowguard docs says why']
    # One region out of date is counted alone (the first region now lists five values); after docs none is.
    _write(tmp_path, {month: 'export function monthly(): number { return 4; }\n'})
    assert said() == ['impact: data.md:11 generate values GRANULARITIES is out of date -> python -m flowguard docs rewrites it']
    assert brief() == ['1 generated region is out of date: python -m flowguard docs rewrites it']
    code, out = _flowguard(tmp_path, 'docs')
    assert code == 0 and out.splitlines() == ['docs/data.md:11 generate values GRANULARITIES: rewritten'], out
    assert brief() == [] and brief('new-task') == []


PT_ROLES = "export const APPLICATION_ROLES = ['SYSTEM_ADMIN', 'PLANNING_ADMIN', 'EMPLOYEE'] as const;\n"
PT_PERMISSIONS = ("import { APPLICATION_ROLES } from '../constants/roles';\n\n"
                  "export type ApplicationRole = (typeof APPLICATION_ROLES)[number];\n")
PT_CENTRAL = """datasource db {
  provider = "sqlserver"
  url      = env("CENTRAL_DATABASE_URL")
}

model CentralEmployee {
  id          String @id
  displayName String @map("display_name")

  @@map("central_employees")
}
"""


def test_a_region_is_named_by_the_set_a_ts_alias_reads_and_by_a_prisma_schema_that_declares_its_model(tmp_path):
    """U3's precision limits, by the files' map facts: a `values` region of a TS alias (`ApplicationRole`, written as
    `(typeof APPLICATION_ROLES)[number]`) is written from the set the alias names, so an edit of that set's own file
    names it; a `fields Customer` region reads only the Prisma schemas that declare Customer, so an edit of Planning
    Tool's central schema, which has other models, leaves it alone."""
    roles, permissions, schema, central = ('frontend/src/constants/roles.ts', 'frontend/src/types/permissions.ts',
                                           'backend/prisma/schema.prisma', 'backend/prisma/central/schema.prisma')
    doc = ('# Roles\n\n<!-- flowguard: generate values ApplicationRole -->\n- `SYSTEM_ADMIN`\n<!-- flowguard: end -->\n\n'
           '<!-- flowguard: generate fields Customer -->\n<!-- flowguard: end -->\n')
    _commit(tmp_path, {roles: PT_ROLES, permissions: PT_PERMISSIONS, schema: PT_SCHEMA, central: PT_CENTRAL,
                       'docs/roles.md': doc})
    values, fields = (f'impact: roles.md:{line} generate {what} is out of date -> python -m flowguard docs rewrites it'
                      for line, what in ((3, 'values ApplicationRole'), (7, 'fields Customer')))
    def said():
        code, text = _static(tmp_path)
        assert code == 0, text
        return [line for line in _block(text) if 'generate ' in line]
    assert said() == []
    _write(tmp_path, {central: PT_CENTRAL.replace('  id ', '  email       String?\n  id ')})
    assert said() == []                                   # a schema without the model
    _write(tmp_path, {central: PT_CENTRAL, schema: PT_SCHEMA.replace('customerId String', 'customerId String?')})
    assert said() == [fields]
    _write(tmp_path, {schema: PT_SCHEMA, roles: PT_ROLES.replace("'EMPLOYEE'", "'FINANCE_ADMIN', 'EMPLOYEE'")})
    assert said() == [values]                             # the set the alias names, in another file
