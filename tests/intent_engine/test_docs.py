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


def test_a_known_entry_may_name_a_whole_document(tmp_path):
    # Planning Tool's team instructions point to files that are gone (K8): the entry names the document itself.
    known = ('[known.stale-pointers]\nsites = ["docs/rates.md"]\nwhy = "It points to files that are gone"\n'
             'act = "ask"\nask = "Should the pointers be removed?"\n')
    _commit(tmp_path, {'app/a.ts': CODE, 'docs/rates.md': DOC, '.flowguard/known.toml': known})
    _write(tmp_path, {'docs/rates.md': DOC.replace('Nothing here', 'Nothing yet')})
    code, text = _static(tmp_path)
    assert code == 0 and any(line.startswith('known: known.stale-pointers at rates.md -> ask owner') for line in _block(text)), text
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
                       'app/jobs.ts': SOURCE, 'docs/jobs.md': REGIONS})
    _write(tmp_path, {'docs/jobs.md': REGIONS + '\nMore text.\n'})
    code, text = _static(tmp_path)
    block = _block(text)
    assert code == 0 and block[0] == 'impact: jobs.md:3 generate fields Job is out of date -> python -m flowguard docs rewrites it', text
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
    _write(tmp_path, {'app/jobs.ts': SOURCE.replace('MAX_SHARE = 2', 'MAX_SHARE = 3')})
    assert [line for line in _block(_static(tmp_path)[1]) if 'jobs.md' in line] == [
        'impact: jobs.md:23 generate constants app/jobs.ts is out of date -> python -m flowguard docs rewrites it']


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
