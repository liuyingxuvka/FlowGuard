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
