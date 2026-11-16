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
