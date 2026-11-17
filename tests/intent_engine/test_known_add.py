"""`python -m flowguard known add` (5.0): one `.flowguard/known.toml` entry written by the command, its sites the places
of the last run's lines of a finding. Planning Tool's 4.3 upgrade wrote its entries by hand: sites that named nothing,
a `finding` spelt as the line's subject, an id the file already had. Each was red in the next run.
"""
from tests.intent_engine.test_static_check import _block, _commit, _flowguard, _static, _write

A = "export const STATUS = ['open', 'closed'] as const;\nexport function isOpen(s: string): boolean {\n  return s === 'open';\n}\n"
B = "export const STATUS = ['open', 'done'] as const;\nexport function label(s: string): string {\n  return s.toUpperCase();\n}\n"
FINDING = 'declarations:STATUS'


def _known(root):
    path = root / '.flowguard/known.toml'
    return path.read_text(encoding='utf-8') if path.is_file() else None


def _differing(root):
    """A project whose two STATUS declarations differ, and a last run that reported it."""
    _commit(root, {'src/a.ts': A, 'src/b.ts': B})
    code, text = _flowguard(root, 'check', '--static', '--all')
    assert code == 0 and any('STATUS' in line for line in _block(text, everything=True)), text
    code, text = _flowguard(root, 'show', '--last')
    assert f'    finding {FINDING}' in text.splitlines(), text


def test_known_add_writes_an_entry_from_the_findings_places_that_the_next_run_reads(tmp_path):
    _differing(tmp_path)
    code, out = _flowguard(tmp_path, 'known', 'add', FINDING, '--act', 'leave', '--why', 'the two lists differ on purpose')
    assert code == 0, out
    written = _known(tmp_path)
    # The line names its place by line (a.ts:1); the entry names the constant declared there.
    assert written == ('[known.declarations-status]\nsites = ["src/a.ts:STATUS"]\n'
                       'why = "the two lists differ on purpose"\nact = "leave"\nfinding = "declarations:STATUS"\n'), written
    assert out.splitlines() == ['known.declarations-status added to .flowguard/known.toml: act leave, sites src/a.ts:STATUS, '
                                'finding declarations:STATUS',
                                'the next run lists it as loosened, as every new entry whose act is not ask'], out
    # The next run reads it: no input problem, and a change to a site gives the entry's line, not before.
    _commit(tmp_path, {}, message='recorded')
    _write(tmp_path, {'src/a.ts': A.replace("['open', 'closed']", "[\n  'open', 'closed',\n]")})
    code, text = _static(tmp_path)
    assert code == 0 and not [line for line in _block(text) if line.startswith(('red', 'before'))], text
    assert any(line.startswith('known: known.declarations-status') for line in _block(text)), text
    # That run printed the entry's line, not the finding's: known add names the run that lists every finding, copy
    # discovery's included, which check --static leaves out.
    code, out = _flowguard(tmp_path, 'known', 'add', FINDING, '--act', 'leave', '--why', 'x')
    assert code == 2 and ('the last run reported no declarations:STATUS: python -m flowguard check --all reports every '
                          'finding, or name its sites with --site path:symbol') in out, out
    # A second entry of the same finding gets its own id; an id the file has is refused, and the file stays as it was.
    code, out = _flowguard(tmp_path, 'known', 'add', FINDING, '--act', 'ask', '--why', 'which list is right?',
                           '--ask', 'Should both lists be closed?', '--site', 'src/b.ts:STATUS')
    assert code == 0 and '[known.declarations-status-2]' in _known(tmp_path), out
    before = _known(tmp_path)
    code, out = _flowguard(tmp_path, 'known', 'add', FINDING, '--act', 'leave', '--why', 'again', '--id', 'declarations-status')
    assert code == 2 and 'known.declarations-status is already an entry of .flowguard/known.toml' in out and _known(tmp_path) == before, out


def test_known_add_refuses_what_the_next_run_would_read_as_invalid_and_leaves_the_file_alone(tmp_path):
    _differing(tmp_path)
    cases = [
        (['STATUS', '--act', 'leave', '--why', 'x'], 'STATUS is not a finding name'),
        (['values:Job.state', '--act', 'leave', '--why', 'x'], 'the last run reported no values:Job.state'),
        ([FINDING, '--act', 'ask', '--why', 'x'], 'act = "ask" needs ask: the question for the owner'),
        ([FINDING, '--act', 'leave', '--why', 'x', '--site', 'src/a.ts:missing'], 'site src/a.ts:missing names nothing'),
        (['-', '--act', 'leave', '--why', 'x'], 'name its sites with --site path:symbol'),
        (['-', '--act', 'ignore', '--why', 'x', '--site', 'src/a.ts:isOpen'], 'act = "ignore" is only for a finding'),
    ]
    for arguments, said in cases:
        code, out = _flowguard(tmp_path, 'known', 'add', *arguments)
        assert code == 2 and said in out and _known(tmp_path) is None, (arguments, out)
    # A matter no check finds names its sites; an existing file keeps its line endings.
    (tmp_path / '.flowguard/known.toml').write_bytes(b'[known.old]\r\nsites = ["src/b.ts:label"]\r\nwhy = "old"\r\nact = "leave"\r\n')
    code, out = _flowguard(tmp_path, 'known', 'add', '-', '--act', 'ask', '--why', 'the open check is unclear',
                           '--ask', 'Is a closed job open?', '--site', 'src/a.ts:isOpen', '--id', 'open-check')
    assert code == 0, out
    assert (tmp_path / '.flowguard/known.toml').read_bytes() == (
        b'[known.old]\r\nsites = ["src/b.ts:label"]\r\nwhy = "old"\r\nact = "leave"\r\n\r\n[known.open-check]\r\n'
        b'sites = ["src/a.ts:isOpen"]\r\nwhy = "the open check is unclear"\r\nact = "ask"\r\nask = "Is a closed job open?"\r\n')



def test_an_ignore_entry_takes_its_finding_out_of_the_briefs_count_and_a_leave_entry_keeps_it(tmp_path):
    # 4.3: a [structure] decision took its problem out of the session brief's count of open structure problems.
    # 5.0 records the decision in known.toml: act = "ignore" (a false finding, only counted) takes it out as that
    # decision did; act = "leave" keeps it counted, for the problem is still open.
    from flowguard.intent import cache
    from flowguard.intent.config import load_config
    from flowguard.intent.health import brief_lines
    from tests.intent_engine.test_static_check import LABELS
    finding = 'labels:src/a.ts:TYPE_LABELS'
    _commit(tmp_path, {'src/a.ts': LABELS % ('TYPE_LABELS', 'Area'), 'src/b.ts': LABELS % ('KIND_LABELS', 'Areas')})
    def brief():
        code, text = _flowguard(tmp_path, 'check', '--static', '--all')
        assert code == 0, text
        cfg = load_config(tmp_path)
        return cache.structure_summary(cfg)['count'], brief_lines(cfg)
    assert brief() == (1, ['1 open structure issues; highest severity: labels TYPE_LABELS (last check; '
                           'check --static --all lists each with its next step, check --all also copies that drifted apart)'])
    code, out = _flowguard(tmp_path, 'known', 'add', finding, '--act', 'leave', '--why', 'the two tables differ on purpose')
    assert code == 0, out
    assert brief()[0] == 1
    path = tmp_path / '.flowguard/known.toml'
    path.write_text(path.read_text(encoding='utf-8').replace('act = "leave"', 'act = "ignore"'), encoding='utf-8')
    assert brief() == (0, [])
    # an entry of another act beside the ignore entry keeps the problem open, and counted
    code, out = _flowguard(tmp_path, 'known', 'add', finding, '--act', 'fix', '--why', 'one spelling in the next release',
                           '--site', 'src/b.ts:KIND_LABELS')
    assert code == 0, out
    assert brief()[0] == 1


def test_a_site_on_a_sql_file_is_written_read_and_refused_as_a_site_of_any_other_file(tmp_path):
    """Planning Tool (5.0 gate): a site on a .sql file raised KeyError 'models': `known add --site` printed a traceback
    and wrote nothing, the same site written by hand made `check --static` exit 1 with a traceback, and an about marker
    did the same, so the fte_share CHECK could not be a known site. Its constraints.sql holds the CHECKs only in
    comments: a site there names nothing, the usual input problem."""
    from tests.intent_engine.test_catalog import SQL_SITES
    _commit(tmp_path, SQL_SITES)
    code, out = _flowguard(tmp_path, 'known', 'add', '-', '--act', 'ask', '--why', 'the CHECK allows 2, the form 1',
                           '--ask', 'Which upper bound holds?', '--id', 'fte-range',
                           '--site', 'prisma/azure-sql-setup.sql:Assignment.fteShare',
                           '--site', 'prisma/azure-sql-setup.sql:lending_assignments.fte_share')
    assert code == 0 and out.splitlines()[0] == (
        'known.fte-range added to .flowguard/known.toml: act ask, sites prisma/azure-sql-setup.sql:Assignment.fteShare, '
        'prisma/azure-sql-setup.sql:lending_assignments.fte_share'), out
    written = _known(tmp_path)
    nothing = ('site prisma/constraints.sql:Assignment.fteShare names nothing in prisma/constraints.sql: name one table or '
               'table.column of that file (the map reads no table statement in it)')
    code, out = _flowguard(tmp_path, 'known', 'add', '-', '--act', 'ask', '--why', 'x', '--ask', 'y?',
                           '--site', 'prisma/constraints.sql:Assignment.fteShare')
    assert code == 2 and f'known add: {nothing}' in out and 'Traceback' not in out and _known(tmp_path) == written, out
    # The next run reads the entry; an edit of the CHECK's file touches it.
    _commit(tmp_path, {}, message='recorded')
    _write(tmp_path, {'prisma/azure-sql-setup.sql': SQL_SITES['prisma/azure-sql-setup.sql'].replace('<= 2.0000', '<= 3.0000')})
    code, text = _static(tmp_path)
    assert code == 0 and not [line for line in _block(text) if line.startswith('red')], text
    assert any(line.startswith('known: known.fte-range at azure-sql-setup.sql:Assignment.fteShare') for line in _block(text)), text
    # The same site written by hand on the file whose statements are comments is the entry's input problem, red.
    _write(tmp_path, {'.flowguard/known.toml': written + '\n[known.by-hand]\nsites = ["prisma/constraints.sql:Assignment.fteShare"]\n'
                      'why = "x"\nact = "ask"\nask = "y?"\n'})
    code, text = _static(tmp_path)
    assert code == 1 and 'Traceback' not in text and any(line.startswith('red: known.by-hand: site prisma/constraints.sql')
                                                         for line in _block(text)), text
    # An about marker on a .sql file reads the site as known.toml does.
    _write(tmp_path, {'.flowguard/known.toml': written,
                      'docs/limits.md': '# Limits\n\n<!-- flowguard: about prisma/azure-sql-setup.sql:assignments.fte_share -->\n'
                                        'An assignment holds at most two FTE.\n\n'
                                        '<!-- flowguard: about prisma/constraints.sql:assignments.fte_share -->\nThe same.\n'})
    code, text = _static(tmp_path)
    reds = [line for line in _block(text) if line.startswith('red')]
    assert code == 1 and 'Traceback' not in text and len(reds) == 1 and reds[0].startswith(
        'red: about prisma/constraints.sql:assignments.fte_share:'), text
