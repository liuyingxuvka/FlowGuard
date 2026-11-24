"""`.flowguard/rules.toml` and `.flowguard/known.toml` (design 4.4): one parser each, fail-closed (an invalid entry is
a red input finding and counts nothing), sites resolved on the map, what a change loosened in them, and `show rules`."""
from contextlib import closing
import subprocess
import textwrap

import pytest

from flowguard.intent import anchors, cli, owners, signals, sources
from flowguard.intent.config import load_config
from flowguard.intent.signals import deliver
from flowguard.map.requests import store_request
from flowguard.structure import build


def _git(root, *arguments):
    return subprocess.run(['git', '-C', str(root), *arguments], check=True, capture_output=True, text=True, timeout=60).stdout


def _write(root, files):
    for name, text in dict(files).items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(textwrap.dedent(text).lstrip(), encoding='utf-8', newline='\n')


def _commit(root, files=(), message='fixture'):
    _write(root, {'.gitignore': '.flowguard/cache/\n__pycache__/\n', **dict(files)})
    if not (root / '.git').exists():
        _git(root, 'init', '-q', '-b', 'main')
    _git(root, 'add', '.')
    _git(root, '-c', 'user.name=Test', '-c', 'user.email=test@example.invalid', 'commit', '-qm', message)
    return root


RULES = '''
    # The rules in force.
    [rule.three-days]
    text = "A loan lasts at most three days."
    source = 'doc SPEC.md "At most three days."'

    [rule.members]
    text   = "Members pay less."      # the AI's summary
    source = 'R1 "Members pay less than others."'
'''

KNOWN = '''
    [known.scale]
    sites = ["src/fees.py:fee"]
    why = "fee reads two scales"
    act = "ask"
    ask = "Which scale is stored?"

    [known.weeks]
    sites = ["src/fees.py:WEEKS", "src/fees.py:Shop.buy"]
    why = "two week counts"
    act = "leave"
    asked = "2026-11-12"
    fix = "count ISO weeks"
    source = 'doc SPEC.md "At most three days."'
    finding = "same:WEEKS"
'''

PYTHON = '''
    WEEKS = 52


    def fee(days):
        return days * 2


    class Shop:
        def buy(self, n):
            return n
'''


def _project(tmp_path, rules=RULES, known=KNOWN, **files):
    _write(tmp_path, {'SPEC.md': 'At most three days.\n', 'src/fees.py': PYTHON,
                      'pyproject.toml': '[tool.flowguard]\nauthority_docs = ["SPEC.md"]\n', **files})
    if rules is not None:
        _write(tmp_path, {'.flowguard/rules.toml': rules})
    if known is not None:
        _write(tmp_path, {'.flowguard/known.toml': known})
    return load_config(tmp_path)


def test_a_valid_catalog_is_read_in_file_order_with_its_lines(tmp_path):
    found = sources.catalog(_project(tmp_path))
    assert found.issues == [], found.issues
    assert list(found.rules) == ['three-days', 'members']
    assert found.rules['members'] == sources.CatalogRule('members', 'Members pay less.', 'R1 "Members pay less than others."', 6)
    assert list(found.known) == ['scale', 'weeks']
    assert found.known['scale'] == sources.Known('scale', ('src/fees.py:fee',), 'fee reads two scales', 'ask',
                                                 ask='Which scale is stored?', line=1)
    weeks = found.known['weeks']
    assert (weeks.sites, weeks.act, weeks.asked, weeks.fix, weeks.finding, weeks.line) == (
        ('src/fees.py:WEEKS', 'src/fees.py:Shop.buy'), 'leave', '2026-11-12', 'count ISO weeks', 'same:WEEKS', 7)
    assert weeks.source == 'doc SPEC.md "At most three days."'


def _problems(found, name):
    issue = next(issue for issue in found.issues if issue.name == name)
    assert issue.family == 'input' and issue.fresh == frozenset({''}) and len(issue.parts) == 1, issue
    return issue.parts[0][2]


@pytest.mark.parametrize('entry, problem', [
    ('text = "x"\nsource = \'R1 "w"\'\nwhy = "y"\n', 'unknown key why (a rule has only text and source)'),
    ('source = \'R1 "w"\'\n', 'missing text'),
    ('text = "x"\n', 'missing source'),
    ('text = """two\nlines"""\nsource = \'R1 "w"\'\n', 'text is one line of words'),
    ('text = 3\nsource = \'R1 "w"\'\n', 'text is one line of words'),
    ('text = " "\nsource = \'R1 "w"\'\n', 'text is one line of words'),
    ('text = "x"\nsource = \'owner R1: w\'\n', "source 'owner R1: w' is neither R<id> \"exact words\", R<id> picked \"exact words\" nor doc PATH \"exact words\""),
    ('text = "x"\nsource = \'R1 words\'\n', "source 'R1 words' is neither R<id> \"exact words\", R<id> picked \"exact words\" nor doc PATH \"exact words\""),
    # R105-5: a pick without its words between double quotes says where they go.
    ('text = "x"\nsource = "R1 picked \'Keep one version\'"\n', 'source "R1 picked \'Keep one version\'" names a pick: the option\'s words go between double quotes, R1 picked "exact words"'),
    # ... and one whose words are between them names the text after them.
    ('text = "x"\nsource = \'R1 picked "Keep one version" (A)\'\n', 'source \'R1 picked "Keep one version" (A)\' names a pick with text after the closing double quote of its words: \' (A)\''),
    ('text = "x"\nsource = \'rule.other\'\n', "source rule.other cites another catalog entry: quote the owner's words or a document instead"),
    ('text = "x"\nsource = 1\n', 'source is a string R<id> "exact words", R<id> picked "exact words" or doc PATH "exact words", not 1'),
])
def test_every_invalid_rule_entry_is_an_input_finding_and_counts_nothing(tmp_path, entry, problem):
    found = sources.catalog(_project(tmp_path, rules='[rule.x]\n' + entry + '\n[rule.ok]\ntext = "y"\nsource = \'R1 "w"\'\n', known=None))
    assert list(found.rules) == ['ok']
    assert problem in _problems(found, 'rules-entry:rule.x').split('; ')
    issue = next(issue for issue in found.issues if issue.name == 'rules-entry:rule.x')
    # the entry is the line's subject and place, named once: `red: rule.x: missing source -> ...`
    assert issue.parts[0][1] == ('.flowguard/rules.toml:rule.x',) and issue.subject == 'rule.x' and issue.files == {'.flowguard/rules.toml'}
    assert issue.rank == 0 and issue.fresh == {''}    # only the 4.3 lines report it, red in every run: no structure count


@pytest.mark.parametrize('text, name, problem', [
    ('[rule.x\n', 'rules-file:.flowguard/rules.toml', 'not TOML: '),
    ('[rules.x]\ntext = "x"\n', 'rules-file:.flowguard/rules.toml', 'holds only [rule.<id>] tables, not rules'),
    ('rule = "x"\n', 'rules-file:.flowguard/rules.toml', "holds only [rule.<id>] tables, not 'x'"),
    ('[rule]\nx = "y"\n', 'rules-entry:rule.x', "[rule.x] is a table of keys, not 'y'"),
    ('[rule."a b"]\ntext = "x"\nsource = \'R1 "w"\'\n', 'rules-entry:rule.a b', "the id 'a b' is letters, digits, - and _"),
])
def test_a_rules_file_that_is_no_table_of_rule_entries_is_an_input_finding(tmp_path, text, name, problem):
    found = sources.catalog(_project(tmp_path, rules=text, known=None))
    assert found.rules == {} and _problems(found, name).startswith(problem), found.issues


def test_bytes_that_are_not_utf8_are_an_input_finding_too(tmp_path):
    cfg = _project(tmp_path, rules=None, known=None)
    (tmp_path / '.flowguard').mkdir()
    (tmp_path / '.flowguard/known.toml').write_bytes(b'[known.x]\nwhy = "\xff"\n')
    found = sources.catalog(cfg)
    assert found.known == {} and _problems(found, 'known-file:.flowguard/known.toml').startswith('not TOML: ')



def test_the_red_of_an_invalid_entry_or_file_names_it_once(tmp_path, capsys):
    """The entry (or file) is the line's subject; the line does not name it a second time as its place."""
    _project(tmp_path, rules='rule = 1\n', known=KNOWN + '''
        [known.night-transfer]
        sites = ["src/fees.py:fee"]
        why = "transfers after midnight"
        act = "later"
    ''')
    _commit(tmp_path)
    assert cli.main(['--root', str(tmp_path), 'check', '--static']) == 1
    assert capsys.readouterr().out.splitlines()[1:] == [
        "red: rules.toml: holds only [rule.<id>] tables, not 1 -> move each entry under [rule.<id>] in rules.toml",
        "red: known.night-transfer: act is one of leave, ask, fix, ignore, not 'later' -> correct [known.night-transfer] in known.toml"]

BASE = 'sites = ["src/fees.py:fee"]\nwhy = "w"\nact = "leave"\n'


@pytest.mark.parametrize('entry, problem', [
    ('why = "w"\nact = "leave"\n', 'missing sites'),
    ('sites = ["src/fees.py:fee"]\nact = "leave"\n', 'missing why'),
    ('sites = ["src/fees.py:fee"]\nwhy = "w"\n', 'missing act'),
    (BASE + 'kind = "x"\n', 'unknown key kind (known.toml entries have sites, why, act, ask, asked, fix, source, finding)'),
    (BASE.replace('["src/fees.py:fee"]', '[]'), 'sites is a non-empty list of path:symbol'),
    (BASE.replace('["src/fees.py:fee"]', '"src/fees.py:fee"'), 'sites is a non-empty list of path:symbol'),
    (BASE.replace('["src/fees.py:fee"]', '[3]'), 'a site is a string path:symbol, not 3'),
    (BASE.replace('src/fees.py:fee', 'fee'), 'site fee is a bare name: write path:symbol, the path relative to the repository'),
    (BASE.replace('src/fees.py:fee', '/src/fees.py:fee'), 'site /src/fees.py:fee needs a repository-relative path before the colon (forward slashes, no ..)'),
    (BASE.replace('src/fees.py:fee', 'src/../fees.py:fee'), 'site src/../fees.py:fee needs a repository-relative path before the colon (forward slashes, no ..)'),
    (BASE.replace('src/fees.py:fee', 'src\\\\fees.py:fee'), 'site src\\fees.py:fee needs a repository-relative path before the colon (forward slashes, no ..)'),
    (BASE.replace('src/fees.py:fee', 'src/fees.py:'), 'site src/fees.py: needs a function, object.method, constant or Model.field after the colon'),
    (BASE.replace('src/fees.py:fee', 'src/gone.py:fee'), 'site src/gone.py:fee: src/gone.py is not a file of this repository'),
    (BASE.replace('"w"', '" "'), 'why says what the matter is: it is empty'),
    (BASE.replace('"leave"', '"maybe"'), "act is one of leave, ask, fix, ignore, not 'maybe'"),
    (BASE.replace('"leave"', '"ask"'), 'act = "ask" needs ask: the question for the owner'),
    (BASE + 'asked = "12.11.2026"\n', "asked is a date written YYYY-MM-DD, not '12.11.2026'"),
    (BASE + 'asked = "2026-02-30"\n', 'asked 2026-02-30 is no calendar date'),
    (BASE + 'ask = 3\n', 'ask is a string, not 3'),
    (BASE + 'finding = "pairs:A>B"\n', 'finding pairs:A>B names no finding FlowGuard reports (pair:, values:, same:, ...)'),
    (BASE.replace('"leave"', '"ignore"'), 'act = "ignore" is only for a finding of an automatic structure check'),
    (BASE.replace('"leave"', '"ignore"') + 'finding = "pair:A>B"\n', 'act = "ignore" is only for a finding of an automatic structure check'),
    (BASE.replace('"leave"', '"ignore"') + 'finding = "same:WEEKS"\n', 'act = "ignore" is only for a finding of an automatic structure check'),
    (BASE + "source = 'assumed: x'\n", "source 'assumed: x' is neither R<id> \"exact words\", R<id> picked \"exact words\" nor doc PATH \"exact words\""),
    (BASE + 'source = "R1 picked \'Keep one version\'"\n', 'source "R1 picked \'Keep one version\'" names a pick: the option\'s words go between double quotes, R1 picked "exact words"'),
    # A valid site beside an invalid one does not make the entry count.
    (BASE.replace('["src/fees.py:fee"]', '["src/fees.py:fee", "fee"]'), 'site fee is a bare name: write path:symbol, the path relative to the repository'),
])
def test_every_invalid_known_entry_is_an_input_finding_and_counts_nothing(tmp_path, entry, problem):
    found = sources.catalog(_project(tmp_path, rules=None, known='[known.x]\n' + entry + '\n[known.ok]\n' + BASE))
    assert list(found.known) == ['ok'], found
    problems = _problems(found, 'known-entry:known.x').split('; ')
    assert any(item.startswith(problem) for item in problems), problems


def test_an_ignore_entry_of_a_structure_finding_is_valid(tmp_path):
    entry = BASE.replace('"leave"', '"ignore"') + 'finding = "delete:Order"\n'
    found = sources.catalog(_project(tmp_path, rules=None, known='[known.x]\n' + entry))
    assert found.issues == [] and found.known['x'].act == 'ignore'


SITES = {
    'src/fees.py': PYTHON,
    'src/orders.py': '''
        class Order:
            status: str = 'new'


        def pay(order: Order):
            order.status = 'paid'
    ''',
    'web/a.ts': '''
        export const GRACE_DAYS = 14;
        export function overdue(days: number) { return days > GRACE_DAYS; }
        export const service = {
          update(x: number) { return x + 1; },
        };
        export class Repo {
          save(x: number) { return x; }
        }
    ''',
    'web/store.ts': '''
        import { PrismaClient } from '@prisma/client';
        const prisma = new PrismaClient();
        export async function setValue(id: string, value: number) {
          return prisma.entry.update({ where: { id }, data: { value } });
        }
    ''',
    'prisma/schema.prisma': '''
        datasource db {
          provider = "postgresql"
          url      = env("DATABASE_URL")
        }
        model Entry {
          id    String @id
          value Float
        }
    ''',
    'package.json': '{"name": "web", "dependencies": {"@prisma/client": "5.0.0"}}\n',
    'README.md': 'Not code.\n',
}


def _resolved(tmp_path, sites, files=SITES):
    cfg = _project(tmp_path, rules=None, known='[known.x]\nsites = ' + repr(list(sites)).replace("'", '"')
                   + '\nwhy = "w"\nact = "leave"\n', **files)
    found = sources.catalog(cfg)
    assert found.issues == [], found.issues
    with closing(build(tmp_path, workers=1)) as graph:
        return sources.known_sites(graph, found.known.values())


@pytest.mark.parametrize('site, node', [
    ('src/fees.py:fee', 'src.fees:fee'),                         # a Python function
    ('src/fees.py:Shop.buy', 'src.fees:Shop.buy'),               # a Python method
    ('src/fees.py:WEEKS', 'src.fees:WEEKS'),                     # a Python constant
    ('web/a.ts:overdue', 'typescript/web/a.ts:overdue'),         # a TS function
    ('web/a.ts:Repo.save', 'typescript/web/a.ts:Repo.save'),     # a TS class method
    ('web/a.ts:service.update', 'typescript/web/a.ts:update'),   # a TS object's method (holder.method)
    ('web/a.ts:GRACE_DAYS', 'typescript/web/a.ts:GRACE_DAYS'),   # a TS constant
])
def test_a_site_resolves_to_its_one_declaration(tmp_path, site, node):
    resolved, issues = _resolved(tmp_path, [site])
    assert issues == [] and [(entry.nodes, entry.files) for entry in resolved] == [(frozenset({node}), frozenset())], resolved


def test_a_model_field_site_resolves_to_its_writers_and_its_schema_file(tmp_path):
    resolved, issues = _resolved(tmp_path, ['prisma/schema.prisma:Entry.value'])
    assert issues == [] and [(entry.nodes, entry.files) for entry in resolved] == [
        (frozenset({'typescript/web/store.ts:setValue'}), frozenset({'prisma/schema.prisma'}))], resolved


def test_a_python_class_field_site_resolves_to_its_writers_and_the_file_of_its_class(tmp_path):
    resolved, issues = _resolved(tmp_path, ['src/orders.py:Order.status'])
    assert issues == [] and [(entry.nodes, entry.files) for entry in resolved] == [
        (frozenset({'src.orders:Order', 'src.orders:pay'}), frozenset({'src/orders.py'}))], (resolved, issues)


@pytest.mark.parametrize('site, problem', [
    ('src/orders.py:Order.gone', 'site src/orders.py:Order.gone names nothing'),      # no write binds the field
    ('src/fees.py:Order.status', 'site src/fees.py:Order.status names nothing'),      # its class is in another file
    ('src/fees.py:missing', 'site src/fees.py:missing names nothing in src/fees.py: name one function, object.method, constant or Model.field of that file'),
    ('src/fees.py:Shop', 'site src/fees.py:Shop names nothing in src/fees.py'),               # a class is no site
    ('web/a.ts:update', 'site web/a.ts:update names nothing in web/a.ts'),                    # the holder belongs to it
    ('prisma/schema.prisma:Entry', 'site prisma/schema.prisma:Entry names nothing'),          # a model alone is no site
    ('prisma/schema.prisma:Entry.gone', 'site prisma/schema.prisma:Entry.gone names nothing'),
    ('README.md:intro', 'site README.md:intro: the map reads no README.md (excluded, or no source or schema file)'),
])
def test_a_site_that_names_no_single_declaration_is_an_input_finding(tmp_path, site, problem):
    resolved, issues = _resolved(tmp_path, ['src/fees.py:fee', site])
    assert resolved == [] and [issue.name for issue in issues] == ['known-entry:known.x'], issues
    assert issues[0].parts[0][2].startswith(problem), issues[0].parts


# Planning Tool (5.0 gate): a site on a .sql file raised KeyError 'models' in known add, in check --static and in an
# about marker. Its prisma/constraints.sql holds its CHECKs only in comments; azure-sql-setup.sql creates the tables
# in T-SQL with a CHECK on fte_share and adds one to a table another file creates.
SQL_SITES = {
    'prisma/schema.prisma': '''
        datasource db {
          provider = "postgresql"
          url      = env("DATABASE_URL")
        }
        model Assignment {
          id       String  @id
          fteShare Decimal @map("fte_share")
          status   String
          @@map("assignments")
        }
    ''',
    'prisma/constraints.sql': '''
        -- 6. assignments: FTE share must be between 0 and 2
        -- CHECK (fte_share >= 0.0000 AND fte_share <= 2.0000)
        /*
        ALTER TABLE assignments ADD CONSTRAINT chk_assignment_fte_range CHECK (fte_share >= 0.0000 AND fte_share <= 2.0000);
        */
    ''',
    'prisma/azure-sql-setup.sql': '''
        CREATE TABLE [dbo].[assignments] (
            [id]        NVARCHAR(36) NOT NULL,
            [fte_share] DECIMAL(6,4) NOT NULL,
            CONSTRAINT [chk_assignment_fte_range] CHECK ([fte_share] >= 0.0000 AND [fte_share] <= 2.0000)
        );
        GO
        ALTER TABLE lending_assignments ADD CONSTRAINT chk_lending_fte_range CHECK (fte_share >= 0.0000 AND fte_share <= 1.0000);
    ''',
    'web/assign.ts': '''
        import { PrismaClient } from '@prisma/client';
        const prisma = new PrismaClient();
        export async function setShare(id: string, fteShare: number) {
          return prisma.assignment.update({ where: { id }, data: { fteShare } });
        }
    ''',
    'package.json': '{"name": "web", "dependencies": {"@prisma/client": "5.0.0"}}\n',
}


@pytest.mark.parametrize('site, nodes', [
    ('prisma/azure-sql-setup.sql:assignments.fte_share', {'typescript/web/assign.ts:setShare'}),
    ('prisma/azure-sql-setup.sql:Assignment.fteShare', {'typescript/web/assign.ts:setShare'}),   # the Prisma names
    ('prisma/azure-sql-setup.sql:ASSIGNMENTS.FTE_SHARE', {'typescript/web/assign.ts:setShare'}),  # SQL ignores case
    ('prisma/azure-sql-setup.sql:assignments', {'typescript/web/assign.ts:setShare'}),           # a table
    ('prisma/azure-sql-setup.sql:lending_assignments.fte_share', set()),     # an ALTER's CHECK on another file's table
])
def test_a_site_on_a_sql_file_names_a_table_or_column_its_statements_name(tmp_path, site, nodes):
    resolved, issues = _resolved(tmp_path, [site], SQL_SITES)
    assert issues == [] and [(entry.nodes, entry.files) for entry in resolved] == [
        (frozenset(nodes), frozenset({'prisma/azure-sql-setup.sql'}))], (resolved, issues)


@pytest.mark.parametrize('site, problem', [
    ('prisma/constraints.sql:Assignment.fteShare', 'site prisma/constraints.sql:Assignment.fteShare names nothing in '
     'prisma/constraints.sql: name one table or table.column of that file (the map reads no table statement in it)'),
    ('prisma/azure-sql-setup.sql:assignments.gone', 'site prisma/azure-sql-setup.sql:assignments.gone names nothing in '
     'prisma/azure-sql-setup.sql: name one table or table.column of that file'),
    ('prisma/azure-sql-setup.sql:Assignment.status', 'site prisma/azure-sql-setup.sql:Assignment.status names nothing in '
     'prisma/azure-sql-setup.sql: name one table or table.column of that file'),     # a field the file has no column of
])
def test_a_sql_site_that_names_nothing_is_the_usual_input_finding(tmp_path, site, problem):
    resolved, issues = _resolved(tmp_path, [site], SQL_SITES)
    assert resolved == [] and [issue.name for issue in issues] == ['known-entry:known.x'], issues
    assert issues[0].parts[0][2] == problem, issues[0].parts


# Design 4.4: a site's symbol may be a constant, whatever its value. Round 23: Planning Tool's zod schema
# `export const projectRequestCreateSchema = z.object(...)`, `APPLICATION_ROLES = [...]` and `appConfig = {...}`
# named nothing, as the map keeps a node only for a constant of a literal value.
CONSTANTS = {
    'web/c.ts': '''
        import { z } from 'zod';
        import { memo } from 'react';
        export const projectRequestCreateSchema = z.object({ name: z.string() });
        export const APPLICATION_ROLES = ['ADMIN', 'USER'] as const;
        export const appConfig = { port: 3000 };
        export let counter = 0;
        var legacy = 1;
        export const Badge = memo(() => 1);
        var twice = 1;
        var twice = 2;
        export function roles() { return APPLICATION_ROLES; }
    ''',
    'src/settings.py': '''
        defaults = {"grace_days": 3}
        limit = 1
        limit = 2
        if True:
            fallback = [1]
        else:
            fallback = [2]


        def grace():
            return defaults["grace_days"]


        grace = None
    ''',
}


@pytest.mark.parametrize('site', ['web/c.ts:projectRequestCreateSchema', 'web/c.ts:APPLICATION_ROLES', 'web/c.ts:appConfig',
                                  'web/c.ts:counter', 'web/c.ts:legacy', 'web/c.ts:Badge', 'src/settings.py:defaults'])
def test_a_module_level_constant_of_any_value_is_a_site(tmp_path, site):
    resolved, issues = _resolved(tmp_path, [site], CONSTANTS)
    assert issues == [] and [entry.sites for entry in resolved] == [(site,)], issues


@pytest.mark.parametrize('site, problem', [
    ('web/c.ts:twice', 'site web/c.ts:twice names 2 declarations in web/c.ts'),
    ('src/settings.py:limit', 'site src/settings.py:limit names 2 declarations in src/settings.py'),
    ('src/settings.py:fallback', 'site src/settings.py:fallback names 2 declarations in src/settings.py'),
    ('src/settings.py:grace', 'site src/settings.py:grace names 2 declarations in src/settings.py'),   # a def and a value
    ('web/c.ts:z', 'site web/c.ts:z names nothing in web/c.ts'),                       # an import declares no constant
    ('web/c.ts:port', 'site web/c.ts:port names nothing in web/c.ts'),                 # nor does an object's key
    ('src/settings.py:grace_days', 'site src/settings.py:grace_days names nothing in src/settings.py'),
])
def test_a_constant_site_still_names_exactly_one_declaration(tmp_path, site, problem):
    resolved, issues = _resolved(tmp_path, ['src/fees.py:fee', site], {**SITES, **CONSTANTS})
    assert resolved == [] and [issue.name for issue in issues] == ['known-entry:known.x'], issues
    assert issues[0].parts[0][2].startswith(problem), issues[0].parts


def test_a_constant_site_is_touched_when_this_change_edits_its_declaration(tmp_path):
    known = '''
        [known.roles]
        sites = ["web/c.ts:APPLICATION_ROLES"]
        why = "two role lists"
        act = "ask"
        ask = "Which roles exist?"

        [known.grace]
        sites = ["src/settings.py:defaults"]
        why = "grace read on two scales"
        act = "leave"
    '''
    cfg = _project(tmp_path, rules=None, known=known, **CONSTANTS)
    _commit(tmp_path)
    base = _git(tmp_path, 'rev-parse', 'HEAD').strip()
    def known_lines(ts, py):
        _write(tmp_path, {'web/c.ts': ts, 'src/settings.py': py})
        with closing(build(tmp_path, workers=1)) as graph:
            found = owners.static_findings(cfg, graph, anchors.collect(graph), base)
        lines, _ = deliver(found.issues, touched_functions=found.touched_functions, touched_files=found.touched_files,
                           known=found.known, ran=found.ran, extra=found.lines)
        return [line.text for line in lines if line.kind == 'known']
    ts, py = CONSTANTS['web/c.ts'], CONSTANTS['src/settings.py']
    # Another declaration of the same files changed: neither entry's site is touched.
    assert known_lines(ts.replace('port: 3000', 'port: 3001'), py.replace('limit = 2', 'limit = 3')) == []
    # Each site's own declaration edited: its entry's line, as for a function site.
    assert known_lines(ts.replace("'USER'", "'GUEST'"), py.replace('"grace_days": 3', '"grace_days": 4')) == [
        'known.roles at web/c.ts:APPLICATION_ROLES: Which roles exist?', 'known.grace at src/settings.py:defaults']


def test_static_findings_carry_the_resolved_entries_input_findings_and_sources_that_do_not_hold(tmp_path):
    cfg = _project(tmp_path, rules=RULES + '''
        [rule.bad]
        text = "x"
    ''', known=KNOWN + '''
        [known.unresolved]
        sites = ["src/fees.py:nothing"]
        why = "w"
        act = "fix"
    ''')
    _commit(tmp_path)
    with closing(build(tmp_path, workers=1)) as graph:
        found = owners.static_findings(cfg, graph, anchors.collect(graph))
    assert sorted(entry.id for entry in found.known) == ['scale', 'weeks']
    weeks = next(entry for entry in found.known if entry.id == 'weeks')
    assert weeks.nodes == {'src.fees:WEEKS', 'src.fees:Shop.buy'}
    catalog = {issue.name: issue for issue in found.issues if issue.family in ('input', 'source')}
    # R1 is not stored: its rule cites nothing; the rule without a source and the site that names nothing are input.
    assert set(catalog) == {'rules-entry:rule.bad', 'known-entry:known.unresolved', 'source:rule.members'}, catalog
    members = catalog['source:rule.members']
    assert members.parts == (('', '.flowguard/rules.toml:rule.members', 'R1 is not stored',
                              "store the owner's words with python -m flowguard req add - --id R1"),)
    assert members.subject == 'source rule.members' and members.files == {'.flowguard/rules.toml', '.flowguard/requests/R1.md'}
    # Nothing changed since the baseline commit, so the old source finding is not new: no red line, and before only
    # when the change touches it; the input findings are red in every run (D4).
    assert members.fresh == frozenset()
    lines, _ = deliver([issue for issue in catalog.values()], touched_functions=(), touched_files=())
    assert [(line.kind, line.name) for line in lines] == [('red', 'rules-entry:rule.bad'), ('red', 'known-entry:known.unresolved')]
    lines, _ = deliver([members], touched_functions=(), touched_files={'.flowguard/rules.toml'})
    assert [(line.kind, line.text) for line in lines] == [
        ('before', 'source rule.members at .flowguard/rules.toml:rule.members was broken at task start')], lines


def test_without_a_catalog_file_static_findings_read_nothing_of_it(tmp_path):
    cfg = _project(tmp_path, rules=None, known=None)
    _commit(tmp_path)
    with closing(build(tmp_path, workers=1)) as graph:
        found = sources.findings(cfg, graph, owners.Change(cfg, graph, None))
    assert (found.issues, found.known) == ([], [])


def test_the_static_findings_carry_what_the_change_loosened_in_the_catalog(tmp_path):
    cfg = _project(tmp_path)
    _commit(tmp_path)
    base = _git(tmp_path, 'rev-parse', 'HEAD').strip()
    _write(tmp_path, {'.flowguard/known.toml': KNOWN.replace('why = "two week counts"', 'why = "one week count"')})
    with closing(build(tmp_path, workers=1)) as graph:
        found = owners.static_findings(cfg, graph, anchors.collect(graph), base)
    assert [(line.kind, line.text) for line in found.lines if line.name.startswith('loosened:known')] == [
        ('loosened', 'known.weeks changed (why)')], found.lines
    # Both files deleted: every rule and entry they held is loosened.
    (tmp_path / '.flowguard/rules.toml').unlink()
    (tmp_path / '.flowguard/known.toml').unlink()
    with closing(build(tmp_path, workers=1)) as graph:
        found = owners.static_findings(cfg, graph, anchors.collect(graph), base)
    assert [line.name for line in found.lines if line.kind == 'loosened'] == [
        'loosened:rule.three-days', 'loosened:rule.members', 'loosened:known.scale', 'loosened:known.weeks'], found.lines


def _lines(old, new):
    return [(line.kind, line.name, line.text, line.step) for line in sources.loosened(old, new)]


def test_what_a_change_loosens_in_the_catalog(tmp_path):
    cfg = _project(tmp_path, known=KNOWN + '''
        [known.gone]
        sites = ["src/fees.py:fee"]
        why = "w"
        act = "fix"
    ''')
    _commit(tmp_path)
    head = _git(tmp_path, 'rev-parse', 'HEAD').strip()
    old = sources.catalog(cfg, head)
    assert sources.loosened(old, sources.catalog(cfg)) == []
    step = "name it in your report; loosening an agreement is the owner's decision"
    # A rule's text or source changed is not loosened; a rule removed is.
    _write(tmp_path, {'.flowguard/rules.toml': RULES.replace('Members pay less.', 'Members pay less, always.').replace(
        '[rule.three-days]\n    text = "A loan lasts at most three days."\n    source = \'doc SPEC.md "At most three days."\'\n', '')})
    # Writing asked is no loosening; changing anything else is, and so is removing an entry or adding one that is
    # not a question for the owner.
    _write(tmp_path, {'.flowguard/known.toml': KNOWN.replace('ask = "Which scale is stored?"', 'ask = "Which scale is stored?"\n    asked = "2026-11-13"')
                      .replace('why = "two week counts"', 'why = "two week counts in two files"') + '''
        [known.question]
        sites = ["src/fees.py:fee"]
        why = "w"
        act = "ask"
        ask = "q?"

        [known.deferred]
        sites = ["src/fees.py:fee"]
        why = "w"
        act = "leave"
    '''})
    assert _lines(old, sources.catalog(cfg)) == [
        ('loosened', 'loosened:rule.three-days', 'rule.three-days removed from .flowguard/rules.toml', step),
        ('loosened', 'loosened:known.weeks', 'known.weeks changed (why)', step),
        ('loosened', 'loosened:known.gone', 'known.gone removed from .flowguard/known.toml', step),
        ('loosened', 'loosened:known.deferred', 'known.deferred added with act = "leave"', step)]
    # An entry that is invalid now is an input finding, not a loosening as well.
    _write(tmp_path, {'.flowguard/known.toml': KNOWN.replace('act = "leave"', 'act = "later"')})
    assert _lines(old, sources.catalog(cfg))[-1:] == [('loosened', 'loosened:known.gone', 'known.gone removed from .flowguard/known.toml', step)]
    _write(tmp_path, {'.flowguard/rules.toml': '[rule.x\n'})
    assert [name for _, name, _, _ in _lines(old, sources.catalog(cfg))] == ['loosened:known.gone']


def test_a_static_check_compares_the_catalog_with_the_baseline_s_and_without_a_baseline_compares_nothing(tmp_path):
    cfg = _project(tmp_path)
    _commit(tmp_path)
    head = _git(tmp_path, 'rev-parse', 'HEAD').strip()
    (tmp_path / '.flowguard/known.toml').unlink()
    (tmp_path / '.flowguard/rules.toml').unlink()
    with closing(build(tmp_path, workers=1)) as graph:
        moved = sources.catalog_loosened(cfg, owners.Change(cfg, graph, head))
        assert [line.name for line in moved] == ['loosened:rule.three-days', 'loosened:rule.members',
                                                 'loosened:known.scale', 'loosened:known.weeks'], moved
        assert sources.catalog_loosened(cfg, owners.Change(cfg, graph, None)) == []


def test_show_rules_lists_each_rule_its_source_and_the_intent_rules_citing_it_then_known_then_input(tmp_path, capsys):
    cfg = _project(tmp_path, known=KNOWN + '''
        [known.unresolved]
        sites = ["src/fees.py:nothing"]
        why = "w"
        act = "fix"
    ''', **{'tests/intent/days.py': '''
        from flowguard.intent import rule


        @rule('DAYS', decides='loan days', fields={'days': int}, source='rule.three-days')
        def DAYS(days):
            return days <= 3
    '''})
    store_request(tmp_path, b'Members pay less than others.\n', identifier='R1')
    _commit(tmp_path)
    assert cli.show(cfg, 'rules') == 1
    lines = capsys.readouterr().out.splitlines()
    assert lines == [
        'FlowGuard rules: 2 in .flowguard/rules.toml, 3 known in .flowguard/known.toml, 1 input problems',
        'rule.three-days: A loan lasts at most three days.',
        '    source: doc SPEC.md "At most three days." (holds)',
        '    cited by tests/intent/days.py:DAYS',
        'rule.members: Members pay less.',
        '    source: R1 "Members pay less than others." (holds)',
        'known.scale: act ask, not asked yet',
        '    why: fee reads two scales',
        '    ask: Which scale is stored?',
        '    site src/fees.py:fee',
        'known.weeks: act leave',
        '    why: two week counts',
        '    fix: count ISO weeks',
        '    site src/fees.py:WEEKS',
        '    site src/fees.py:Shop.buy',
        '    finding same:WEEKS: no run recorded',
        '    source: doc SPEC.md "At most three days." (holds)',
        'known.unresolved: act fix',
        '    why: w',
        '    site src/fees.py:nothing (see the input problem below)',
        'input known-entry:known.unresolved: .flowguard/known.toml:known.unresolved site src/fees.py:nothing names nothing in '
        'src/fees.py: name one function, object.method, constant or Model.field of that file -> correct the sites of '
        '[known.unresolved] in .flowguard/known.toml'], lines
    assert cli.show(cfg, 'rule.three-days') == 0
    assert capsys.readouterr().out.splitlines() == lines[1:4]
    assert cli.show(cfg, 'known.weeks') == 0
    assert capsys.readouterr().out.splitlines() == lines[10:17]
    (tmp_path / 'SPEC.md').write_text('At most four days.\n', encoding='utf-8')
    assert cli.show(cfg, 'rule.three-days') == 0
    assert capsys.readouterr().out.splitlines()[1] == (
        '    source: doc SPEC.md "At most three days." (does not hold: SPEC.md does not contain "At most three days." '
        '-> quote the document exactly)')


def test_show_of_an_entry_names_the_problem_of_its_file(tmp_path, capsys):
    cfg = _project(tmp_path, rules='[rule.three-days]\ntext = "x"\nsource = \'unclosed\n')
    assert cli.show(cfg, 'rule.three-days') == 1
    lines = capsys.readouterr().out.splitlines()
    assert len(lines) == 1 and lines[0].startswith('input rules-file:.flowguard/rules.toml: .flowguard/rules.toml '
                                                   'not TOML: '), lines
    # The other file's problem is not this entry's.
    assert cli.show(cfg, 'known.scale') == 0 and 'rules-file' not in capsys.readouterr().out


# Shaped like Planning Tool's open matters (its known.toml of 2026-11-15): TS services and utils, a Prisma schema, two
# copies of the ISO week count marked `same`, an intent rule anchored on them that cites a rules.toml rule. As there,
# percent-scale names CapacityCalendarEntry.value only in its why, three entries quote the requirements document as
# their source and no site names it, iso-weeks' why is longer than a brief line, and two services each have an
# `update` method (employeeService.update a known site, centralEmployeeService.update not).
CAPACITY = {
    'pyproject.toml': '[tool.flowguard]\nauthority_docs = ["docs/requirements.md"]\n',
    'docs/requirements.md': ('Weekly capacity view aggregated by calendar weeks (KW 1-53).\nA working day has 8 hours.\n'
                             'Capacity unit toggle (hours 0-8 / percent 0-1).\nApproves/rejects project requests.\n'),
    'docs/requests.md': '# Project requests\n\nApproves/rejects project requests.\n',
    'backend/prisma/schema.prisma': '''
        model ProjectRequest {
          id               String  @id
          status           String
          decisionMetadata String?
          @@map("project_requests")
        }

        model CapacityCalendarEntry {
          id    String @id
          unit  String
          value Float
          @@map("capacity_calendar_entries")
        }
    ''',
    'backend/src/utils/capacity-conversion.ts': '''
        export const DAILY_BASELINE_HOURS = 8;

        export function convertPercentToHours(value: number): number {
          return value * DAILY_BASELINE_HOURS;
        }
    ''',
    'backend/src/utils/calendar-iso.ts': '''
        // flowguard: same ISO_WEEKS_IN_YEAR
        export function getIsoWeekCountInYear(year: number): number {
          const day = new Date(Date.UTC(year, 11, 31)).getUTCDay();
          return day === 4 || day === 5 ? 53 : 52;
        }
    ''',
    'backend/src/services/capacity.service.ts': '''
        import { prisma } from '../lib/prisma';
        import { convertPercentToHours } from '../utils/capacity-conversion';

        export const capacityService = {
          async updateCalendarEntry(entryId: string, value: number) {
            const hours = convertPercentToHours(value) / 8;
            return prisma.capacityCalendarEntry.update({ where: { id: entryId }, data: { value: hours } });
          },
        };
    ''',
    'frontend/src/utils/weeks.ts': '''
        // flowguard: same ISO_WEEKS_IN_YEAR
        export function getIsoWeeksInYear(year: number): number {
          const day = new Date(Date.UTC(year, 11, 28)).getUTCDay();
          return day === 4 ? 53 : 52;
        }
    ''',
    'backend/src/services/employee.service.ts': '''
        import { prisma } from '../lib/prisma';

        export const employeeService = {
          async findAll() {
            return prisma.$queryRawUnsafe('SELECT * FROM employees');
          },
          async update(id: string, name: string) {
            return prisma.employee.update({ where: { id }, data: { name } });
          },
        };
    ''',
    'backend/src/services/central-employee.service.ts': '''
        export const centralEmployeeService = {
          async update(id: string, name: string) {
            return { id, name };
          },
        };
    ''',
    'backend/src/services/employee-utilization.service.ts': '''
        export async function updateAssignmentPsp(employeeId: string) {
          return employeeId;
        }
    ''',
    'tests/intent/iso_weeks.py': '''
        from flowguard.intent import rule


        @rule('ISO_WEEKS', decides='iso weeks in a year', fields={'year': int}, anchor='ISO_WEEKS_IN_YEAR',
              source='rule.iso-weeks')
        def ISO_WEEKS(year):
            """A year has 53 ISO weeks when its 28 December falls in week 53."""
            return None
    ''',
    '.flowguard/rules.toml': '''
        [rule.iso-weeks]
        text = "Weekly capacity is aggregated by calendar weeks KW 1 to 53."
        source = 'doc docs/requirements.md "Weekly capacity view aggregated by calendar weeks (KW 1-53)."'

        [rule.hours]
        text = "A working day has 8 hours."
        source = 'doc docs/requirements.md "A working day has 8 hours."'
    ''',
    '.flowguard/known.toml': '''
        [known.hours-constants]
        sites = ["backend/src/utils/capacity-conversion.ts:DAILY_BASELINE_HOURS",
                 "backend/src/services/capacity.service.ts:capacityService.updateCalendarEntry"]
        why   = "8 hours a day is written in the conversion and again in the capacity service"
        act   = "fix"
        fix   = "Read the daily hours from DAILY_BASELINE_HOURS"

        [known.percent-scale]
        sites  = ["backend/src/utils/capacity-conversion.ts:convertPercentToHours",
                  "backend/src/services/capacity.service.ts:capacityService.updateCalendarEntry"]
        why    = "CapacityCalendarEntry.value of PERCENT rows is read on two scales, 0..1 and 0..100"
        act    = "ask"
        asked  = "2026-11-15"
        ask    = "Which scale does the database store for PERCENT rows, 0..1 or 0..100?"
        source = 'doc docs/requirements.md "Capacity unit toggle (hours 0-8 / percent 0-1)."'

        [known.iso-weeks]
        sites   = ["backend/src/utils/calendar-iso.ts:getIsoWeekCountInYear", "frontend/src/utils/weeks.ts:getIsoWeeksInYear"]
        why     = "The backend copy takes the ISO week of 31 December and returns 1 for 2025; the two frontend copies take 28 December and return 52. Left for the bug-fixing pass (commit 36edc17)"
        act     = "leave"
        source  = 'doc docs/requirements.md "Weekly capacity view aggregated by calendar weeks (KW 1-53)."'
        finding = "same:ISO_WEEKS_IN_YEAR"

        [known.project-requests]
        sites  = ["backend/prisma/schema.prisma:ProjectRequest.status", "docs/requests.md"]
        why    = "No route approves or rejects a project request"
        act    = "ask"
        ask    = "Is the project-request workflow retired, or still to be built?"
        source = 'doc docs/requirements.md "Approves/rejects project requests."'

        [known.raw-sql]
        sites = ["backend/src/services/employee.service.ts:employeeService.findAll"]
        why   = "The constitution allows raw SQL only in migration files; these services run raw SQL"
        act   = "ask"
        asked = "2026-11-15"
        ask   = "Should the constitution allow raw SQL in these services, or should the code move to Prisma queries?"

        [known.renumber-order]
        sites = ["backend/src/services/employee.service.ts:employeeService.update"]
        why   = "employeeService.update hands the employee it loaded before the renumbering to the home-unit change"
        act   = "leave"

        [known.entry-writers]
        sites   = ["backend/prisma/schema.prisma:CapacityCalendarEntry.value"]
        why     = "Each service writes its own rows"
        act     = "ignore"
        finding = "writers:CapacityCalendarEntry.value"
    ''',
}

ASKED = ('known.percent-scale: asked the owner on 2026-11-15, no answer yet: Which scale does the database store for PERCENT '
         'rows, 0..1 or 0..100? (python -m flowguard show known.percent-scale)')
OPEN = ('known.project-requests: open question for the owner: Is the project-request workflow retired, or still to be built? '
        '(python -m flowguard show known.project-requests)')
FIX = ('known.hours-constants: to fix when its code changes: 8 hours a day is written in the conversion and again in the '
       'capacity service (python -m flowguard show known.hours-constants)')
# Cut to the brief's width as Planning Tool's own iso-weeks line is, the place to read it whole kept.
LEAVE = ('known.iso-weeks: left as it is: The backend copy takes the ISO week of 31 December and returns 1 for 2025; the two '
         'frontend copies take 28 December and re... (python -m flowguard show known.iso-weeks)')
IGNORE = 'known.entry-writers: ignored, not reported: Each service writes its own rows (python -m flowguard show known.entry-writers)'
RAW = ('known.raw-sql: asked the owner on 2026-11-15, no answer yet: Should the constitution allow raw SQL in these services, '
       'or should the code move to Prisma quer... (python -m flowguard show known.raw-sql)')
RENUMBER = ('known.renumber-order: left as it is: employeeService.update hands the employee it loaded before the renumbering '
            'to the home-unit change (python -m flowguard show known.renumber-order)')
RULE = 'rule ISO_WEEKS: iso weeks in a year'
CITED = ('rule.iso-weeks: Weekly capacity is aggregated by calendar weeks KW 1 to 53. '
         '(python -m flowguard show rule.iso-weeks)')
HOURS = 'rule.hours: A working day has 8 hours. (python -m flowguard show rule.hours)'
SAME = 'same ISO_WEEKS_IN_YEAR backend/src/utils/calendar-iso.ts:2'
NOTICE = 'Map: prisma 1/1 parsed; typescript 7/7 parsed; static facts, foreign native-home execution not verified.'


def _shown(tmp_path, capsys, files):
    _commit(tmp_path, files)
    cfg = load_config(tmp_path)

    def shown(query):
        assert cli.show(cfg, query) == 0
        return capsys.readouterr().out.splitlines()
    return cfg, shown


def _through(line, site):
    """A known line as `show` gives it for an entry named only through the last dotted part of `site`."""
    head, _, rest = line.partition(': ')
    return f'{head} (site {site}): {rest}'


def test_show_of_a_name_or_path_begins_with_the_known_entries_and_rules_that_concern_it(tmp_path, capsys):
    # Planning Tool's agent looked names up with show and saw the open questions about them only in the session brief.
    cfg, shown = _shown(tmp_path, capsys, CAPACITY)
    # The facts branch (a function name, an object.method, a Model.field): after the header and the map notice, the
    # entries in the brief's order (questions not asked yet, asked ones, fix, leave, ignore) with the brief's words, then
    # the intent rules whose anchors name it, the rules.toml rules they cite and the flowguard comment that marks it.
    lines = shown('getIsoWeekCountInYear')
    assert lines[:6] == ['show getIsoWeekCountInYear', NOTICE, LEAVE, RULE, CITED, SAME], lines
    # The rule's word-scored line of this branch is not repeated; the uncited rules.toml rule is not listed.
    assert sum(line.startswith('rule ISO_WEEKS') for line in lines) == 1 and not any('rule.hours' in line for line in lines)
    assert shown('convertPercentToHours')[:3] == ['show convertPercentToHours', NOTICE, ASKED]
    assert shown('capacityService.updateCalendarEntry')[:4] == ['show capacityService.updateCalendarEntry', NOTICE, ASKED, FIX]
    assert shown('ProjectRequest.status')[:3] == ['show ProjectRequest.status', NOTICE, OPEN]
    # A known line is cut to the brief's width, with the place to read the whole entry kept (Planning Tool's iso-weeks).
    assert len(LEAVE) == cli.BRIEF_WIDTH and LEAVE.endswith('re... (python -m flowguard show known.iso-weeks)')
    # Planning Tool's percent-scale names CapacityCalendarEntry.value only in its why: the field's own query lists it,
    # after the entry with a site on the field, in either spelling of the field.
    for query in ('CapacityCalendarEntry.value', 'capacity_calendar_entries.value'):
        assert shown(query)[:4] == [f'show {query}', NOTICE, IGNORE, ASKED]
    # The anchor branch, under the header and the map notice every view has (gate-6): the entry whose finding names
    # the agreement, the rule anchored on it; its copies are the anchor lines that follow, not listed again.
    lines = shown('ISO_WEEKS_IN_YEAR')
    assert lines[:5] == ['show ISO_WEEKS_IN_YEAR', NOTICE, LEAVE, RULE, CITED] and lines[5].startswith('anchor ISO_WEEKS_IN_YEAR -> '), lines
    assert SAME not in lines
    # The module branch (a file, a folder, a document), under the same header and map notice (gate-4): every entry with
    # a site there, the rules anchored there and the flowguard comments written there, then the module's own line; a
    # document, which that line calls one, also lists the entries and rules.toml rules that quote it, and puts no about
    # marker for itself. A folder without a file the map reads says so instead of a module view, and lists no word
    # look-alikes (Planning Tool's docs/requirements gave render_collectors.cjs).
    assert shown('docs/requests.md') == ['show docs/requests.md', NOTICE, OPEN, 'document docs/requests.md']
    assert shown('docs/requirements.md') == ['show docs/requirements.md', NOTICE, OPEN, ASKED, LEAVE, CITED, HOURS,
                                             'document docs/requirements.md']
    assert shown('docs') == ['show docs', NOTICE, OPEN, ASKED, LEAVE, CITED, HOURS,
                             'folder docs/: no source file the map reads; 2 Markdown documents']
    assert shown('backend/prisma/schema.prisma')[:5] == ['show backend/prisma/schema.prisma', NOTICE, OPEN, IGNORE,
                                                         'module backend/prisma/schema.prisma: 1 file, 0 functions']
    lines = shown('backend/src/utils/capacity-conversion.ts')
    assert lines[:6] == ['show backend/src/utils/capacity-conversion.ts', NOTICE, ASKED, FIX,
                         'module backend/src/utils/capacity-conversion.ts: 1 file, 1 function',
                         'described by no text: put <!-- flowguard: about backend/src/utils/capacity-conversion.ts --> '
                         'above the Markdown text that is its contract'], lines
    # A folder with a trailing slash or a leading ./, as a shell completes it, is that folder.
    folder = [NOTICE, ASKED, FIX, LEAVE, RULE, CITED, SAME, 'module backend/src/utils/: 2 files, 2 functions']
    for query in ('backend/src/utils', 'backend/src/utils/', './backend/src/utils/', './backend/src/utils'):
        assert shown(query)[:9] == [f'show {query}', *folder], query
    # The plain node branch: the map's id of the object method its site names, its node view after what concerns it.
    query = 'typescript/backend/src/services/capacity.service.ts:updateCalendarEntry'
    lines = shown(query)
    assert lines[:4] == [f'show {query}', NOTICE, ASKED, FIX] and lines[4].startswith(
        f'{query} backend/src/services/capacity.service.ts:'), lines
    # Nothing concerns these: no known or rule line (project-requests names another field of that model); the map knows
    # no such name and says so.
    assert shown('frobnicateWidgets') == ['show frobnicateWidgets', NOTICE, 'not on the map: no function, class, type, '
                                          'constant, enum, Prisma model or field, or SQL table or column is named '
                                          'frobnicateWidgets']
    lines = shown('ProjectRequest.decisionMetadata')
    assert lines[:2] == ['show ProjectRequest.decisionMetadata', NOTICE] and not [
        line for line in lines if line.startswith(('known.', 'rule'))], lines
    # One function gives the brief and show their words: the brief's line is show's without the place to read it.
    assert cli.screen(cfg) == 0
    brief = capsys.readouterr().out.splitlines()
    assert OPEN.removesuffix(' (python -m flowguard show known.project-requests)') in brief, brief


def test_a_known_line_found_through_a_generic_name_says_which_site_and_a_model_or_object_finds_its_members(tmp_path, capsys):
    # On Planning Tool `show status`, `show update` and `show findAll` printed an entry of one of many same-named
    # functions or fields without saying which, while `show ProjectRequest`, `show capacityService` and
    # `show project_requests.status` printed none.
    _, shown = _shown(tmp_path, capsys, CAPACITY)
    renumber = _through(RENUMBER, 'backend/src/services/employee.service.ts:employeeService.update')
    assert shown('update')[:3] == ['show update', NOTICE, renumber]
    assert shown('findAll')[:3] == ['show findAll', NOTICE, _through(RAW, 'backend/src/services/employee.service.ts:employeeService.findAll')]
    site = 'backend/src/services/capacity.service.ts:capacityService.updateCalendarEntry'
    assert shown('updateCalendarEntry')[:4] == ['show updateCalendarEntry', NOTICE, _through(ASKED, site), _through(FIX, site)]
    assert shown('status')[:3] == ['show status', NOTICE, _through(OPEN, 'backend/prisma/schema.prisma:ProjectRequest.status')]
    # The site's words are added to the brief's line, which is cut as the brief cuts it.
    assert len(renumber) == len(RENUMBER) + len(' (site backend/src/services/employee.service.ts:employeeService.update)')
    # The model or object that holds a site, the table.column of a Prisma field, a name in another letter case: as the
    # entry itself.
    for query in ('ProjectRequest', 'projectRequest', 'project_requests', 'project_requests.status'):
        assert shown(query)[:3] == [f'show {query}', NOTICE, OPEN], query
    assert shown('capacityService')[:4] == ['show capacityService', NOTICE, ASKED, FIX]
    assert shown('employeeService')[:4] == ['show employeeService', NOTICE, RAW, RENUMBER]
    assert shown('convertpercenttohours')[:3] == ['show convertpercenttohours', NOTICE, ASKED]
    # A map node is as precise as before: the other service's update is no site of the entry.
    lines = shown('typescript/backend/src/services/employee.service.ts:update')
    assert lines[lines.index(NOTICE) + 1] == RENUMBER, lines
    lines = shown('typescript/backend/src/services/central-employee.service.ts:update')
    assert not [line for line in lines if line.startswith('known.')], lines


def test_show_of_a_site_as_known_toml_writes_it_gives_its_symbol_s_facts(tmp_path, capsys):
    # `show known.<id>` prints sites as path:symbol; passed to show, Planning Tool's site printed the entry and then only
    # word look-alikes, without the field's declaration or the constant's value.
    _, shown = _shown(tmp_path, capsys, CAPACITY)
    query = 'backend/prisma/schema.prisma:ProjectRequest.status'
    assert shown(query)[:4] == [f'show {query}', NOTICE, OPEN, 'declared ProjectRequest.status: String (backend/prisma/schema.prisma:3)']
    query = 'backend/src/utils/capacity-conversion.ts:DAILY_BASELINE_HOURS'
    assert shown(query)[:4] == [f'show {query}', NOTICE, FIX,
                                'const DAILY_BASELINE_HOURS = 8 (backend/src/utils/capacity-conversion.ts:1)']
    # A function or object method site is the map node of that file: its signature, then what concerns the site.
    query = 'backend/src/services/capacity.service.ts:capacityService.updateCalendarEntry'
    lines = shown(query)
    assert lines[:6] == [f'show {query}', NOTICE, ASKED, FIX, f'{query} backend/src/services/capacity.service.ts:5',
                         'async updateCalendarEntry(entryId: string, value: number) '], lines


def test_an_object_method_query_ranks_that_object_s_method_first(tmp_path, capsys):
    # On Planning Tool `show employeeService.update` listed central-employee.service.ts:update and updateAssignmentPsp
    # before employee.service.ts:update, under the known line about employeeService.update.
    _, shown = _shown(tmp_path, capsys, CAPACITY)
    lines = shown('employeeService.update')
    assert lines[:4] == ['show employeeService.update', NOTICE, RENUMBER,
                         'typescript/backend/src/services/employee.service.ts:update backend/src/services/employee.service.ts:7'], lines
    assert shown('EmployeeService.update')[3] == lines[3]
    assert shown('centralEmployeeService.update')[2].startswith('typescript/backend/src/services/central-employee.service.ts:update ')


# Shaped like Planning Tool's flowguard comments (no intent rules, as there): a writers agreement at the top of a
# service file above a constant, a together agreement right above the function it concerns, one inside an object
# literal above its method, and two `same` copies.
AGREEMENTS = {
    'pyproject.toml': '[tool.flowguard]\n',
    'backend/prisma/schema.prisma': '''
        model Project {
          id                String @id
          name              String
          lifecycleStatusId String @map("lifecycle_status_id")
          @@map("projects")
        }

        model Employee {
          id                   String @id
          organizationalUnitId String @map("organizational_unit_id")
          @@map("employees")
        }

        model CentralEmployee {
          id        String  @id
          orgUnitId String? @map("org_unit_id")
          @@map("central_employees")
        }

        model PspElement {
          id             String  @id
          title          String
          parentPspId    String? @map("parent_psp_id")
          hierarchyLevel Int     @map("hierarchy_level")
          @@map("psp_elements")
        }
    ''',
    'backend/src/services/project.service.ts': '''
        import { prisma } from '../lib/prisma';

        // flowguard: writers Project.lifecycleStatusId projectService.create,projectService.update
        const VALID_TRANSITIONS: Record<string, string[]> = {
          PLANNED: ['ACTIVE'],
          ACTIVE: ['FINISHED'],
        };

        export const projectService = {
          async create(name: string, lifecycleStatusId: string) {
            return prisma.project.create({ data: { name, lifecycleStatusId } });
          },
          async update(id: string, lifecycleStatusId: string) {
            if (!VALID_TRANSITIONS[lifecycleStatusId]) throw new Error('invalid transition');
            return prisma.project.update({ where: { id }, data: { lifecycleStatusId } });
          },
        };
    ''',
    'backend/src/services/employee-home-unit.service.ts': '''
        import { prisma } from '../lib/prisma';

        /**
         * Move an employee to another home unit, locally and in Central.
         */
        // flowguard: together CentralEmployee.orgUnitId Employee.organizationalUnitId
        export async function changeEmployeeHomeUnit(employeeId: string, orgUnitId: string) {
          await prisma.centralEmployee.update({ where: { id: employeeId }, data: { orgUnitId } });
          return prisma.employee.update({ where: { id: employeeId }, data: { organizationalUnitId: orgUnitId } });
        }
    ''',
    'backend/src/services/psp-element.service.ts': '''
        import { prisma } from '../lib/prisma';

        export const pspElementService = {
          // flowguard: together PspElement.parentPspId PspElement.hierarchyLevel
          async create(title: string, parentPspId: string, hierarchyLevel: number) {
            return prisma.pspElement.create({ data: { title, parentPspId, hierarchyLevel } });
          },
          async move(id: string, title: string, parentPspId: string, hierarchyLevel: number) {
            return prisma.pspElement.update({ where: { id }, data: { title, parentPspId, hierarchyLevel } });
          },
        };
    ''',
    'backend/src/utils/calendar-iso.ts': CAPACITY['backend/src/utils/calendar-iso.ts'],
    'frontend/src/utils/weeks.ts': CAPACITY['frontend/src/utils/weeks.ts'],
    '.flowguard/known.toml': '''
        [known.renumber-order]
        sites = ["backend/src/services/employee-home-unit.service.ts:changeEmployeeHomeUnit"]
        why   = "The home-unit change gets the employee loaded before the renumbering"
        act   = "leave"
    ''',
}

WRITERS = ('writers Project.lifecycleStatusId projectService.create,projectService.update '
           'backend/src/services/project.service.ts:3')
HOME = ('together CentralEmployee.orgUnitId Employee.organizationalUnitId '
        'backend/src/services/employee-home-unit.service.ts:6')
PSP = 'together PspElement.parentPspId PspElement.hierarchyLevel backend/src/services/psp-element.service.ts:4'
HOME_KNOWN = ('known.renumber-order: left as it is: The home-unit change gets the employee loaded before the renumbering '
              '(python -m flowguard show known.renumber-order)')
AGREED_NOTICE = 'Map: prisma 1/1 parsed; typescript 5/5 parsed; static facts, foreign native-home execution not verified.'


def test_show_lists_the_flowguard_comment_agreements_that_concern_a_function_file_or_field(tmp_path, capsys):
    # Planning Tool has no intent rules and twelve agreements written as flowguard comments; show of projectService.create,
    # of changeEmployeeHomeUnit, of their files and of a together agreement's partner field named none of them.
    _, shown = _shown(tmp_path, capsys, AGREEMENTS)
    # A function: the agreements that name it (a writers function, its last part too) or that sit right above it.
    assert shown('projectService.create')[:3] == ['show projectService.create', AGREED_NOTICE, WRITERS]
    # A function named only through its last part says which function it is, as a known line says its site.
    assert shown('create')[:4] == ['show create', AGREED_NOTICE,
                                   WRITERS + ' (site backend/src/services/project.service.ts:projectService.create)',
                                   PSP + ' (site backend/src/services/psp-element.service.ts:pspElementService.create)']
    lines = shown('typescript/backend/src/services/project.service.ts:create')
    assert lines[lines.index(AGREED_NOTICE) + 1] == WRITERS, lines
    assert shown('changeEmployeeHomeUnit')[:4] == ['show changeEmployeeHomeUnit', AGREED_NOTICE, HOME_KNOWN, HOME]
    assert shown('pspElementService.create')[:3] == ['show pspElementService.create', AGREED_NOTICE, PSP]
    assert PSP not in shown('pspElementService.move')
    assert shown('getIsoWeekCountInYear')[:3] == ['show getIsoWeekCountInYear', AGREED_NOTICE, SAME]
    # A file or folder: the agreements written there.
    assert shown('backend/src/services/project.service.ts')[:4] == [
        'show backend/src/services/project.service.ts', AGREED_NOTICE, WRITERS,
        'module backend/src/services/project.service.ts: 1 file, 2 functions']
    assert shown('backend/src/services/employee-home-unit.service.ts')[:5] == [
        'show backend/src/services/employee-home-unit.service.ts', AGREED_NOTICE, HOME_KNOWN, HOME,
        'module backend/src/services/employee-home-unit.service.ts: 1 file, 1 function']
    assert shown('backend/src/utils/calendar-iso.ts')[:4] == ['show backend/src/utils/calendar-iso.ts', AGREED_NOTICE, SAME,
                                                              'module backend/src/utils/calendar-iso.ts: 1 file, 1 function']
    assert shown('backend/src/services')[:7] == ['show backend/src/services', AGREED_NOTICE, HOME_KNOWN, HOME, WRITERS, PSP,
                                                 'module backend/src/services/: 3 files, 5 functions']
    # A field: every agreement that names it as its field or partner, in either spelling; the anchor view of an
    # agreement's own field lists it once, as before.
    for query in ('Employee.organizationalUnitId', 'employees.organizational_unit_id'):
        assert shown(query)[:3] == [f'show {query}', AGREED_NOTICE, HOME], query
    assert shown('Employee')[:3] == ['show Employee', AGREED_NOTICE, HOME]
    assert shown('CentralEmployee.orgUnitId').count(HOME) == 1
    # A pair an agreement already holds, in either order, is no together candidate of the partner field.
    lines = shown('PspElement.hierarchyLevel')
    assert lines[:3] == ['show PspElement.hierarchyLevel', AGREED_NOTICE, PSP], lines
    candidates = [line for line in lines if line.startswith('together candidate')]
    assert candidates and all('PspElement.parentPspId' not in line for line in candidates), lines
    assert any('PspElement.title is written by 2 of the 2 functions' in line for line in candidates), lines


# Rules named after the constant and the agreement they decide, a Python states rule and a flow (TD1, TD8).
LIMITS = {
    'pyproject.toml': '[tool.flowguard]\nauthority_docs = ["docs/spec.md"]\n',
    'docs/spec.md': 'A share is at most 2.\nA late day costs 2.\nA hire is open or returned.\n',
    'app/__init__.py': '',
    'app/limits.py': '''
        MAX_SHARE = 2


        def share_ok(share):
            return share <= MAX_SHARE
    ''',
    'app/fees.py': '''
        # flowguard: same FEE
        def late_fee(days):
            return 2 * days


        # flowguard: same FEE
        def preview_fee(days):
            return 3 * days
    ''',
    'app/decision.py': '''
        class Hire:
            def hold(self):
                self.status = 'open'
    ''',
    'tests/intent/policies.py': '''
        from flowguard.intent import Node, flow, rule, states


        @rule('MAX_SHARE', decides='largest share', fields={'share': float}, source='rule.max-share')
        def MAX_SHARE(share):
            return share <= 2


        @rule('FEE', decides='late fee', fields={'days': int}, source='doc docs/spec.md "A late day costs 2."', anchor='FEE')
        def FEE(days):
            return 2 * days


        states('app.decision:Hire.status', ['open', 'returned'], source='doc docs/spec.md "A hire is open or returned."')
        flow('INVOICE', source='assumed: an invoice charges the late fee', nodes=[Node('fee', 'FEE', phase='return')],
             edges=[])
    ''',
    '.flowguard/rules.toml': '''
        [rule.max-share]
        text = "A share is at most 2."
        source = 'doc docs/spec.md "A share is at most 2."'
    ''',
    '.flowguard/known.toml': '''
        [known.share-limit]
        sites = ["app/limits.py:MAX_SHARE"]
        why   = "The frontend allows 2.5"
        act   = "ask"
        ask   = "Is the largest share 2 or 2.5?"

        [known.fee-copies]
        sites   = ["app/fees.py:late_fee", "app/fees.py:preview_fee"]
        why     = "The preview charges 3 per late day, the invoice 2"
        act     = "ask"
        ask     = "Which daily late fee is right, 2 or 3?"
        finding = "same:FEE"

        [known.preview-share]
        sites = ["app/fees.py:preview_fee"]
        why   = "The preview rounds the share before it compares it with MAX_SHARE"
        act   = "leave"

        [known.invoice-order]
        sites   = ["app/fees.py:late_fee"]
        why     = "The invoice flow reads the fee before the discount"
        act     = "leave"
        finding = "flow:INVOICE"
    ''',
}

SHARE = 'known.share-limit: open question for the owner: Is the largest share 2 or 2.5? (python -m flowguard show known.share-limit)'
FEE_COPIES = ('known.fee-copies: open question for the owner: Which daily late fee is right, 2 or 3? '
        '(python -m flowguard show known.fee-copies)')
PREVIEW = ('known.preview-share: left as it is: The preview rounds the share before it compares it with MAX_SHARE '
           '(python -m flowguard show known.preview-share)')
INVOICE = ('known.invoice-order: left as it is: The invoice flow reads the fee before the discount '
           '(python -m flowguard show known.invoice-order)')
STATES = 'rule states:app.decision:Hire.status: app.decision:Hire.status'


def test_a_rule_or_flow_view_and_a_python_rule_home_begin_with_what_concerns_them(tmp_path, capsys):
    # A rule named after the constant or the agreement it decides took the RULE branch, which printed no known line.
    _, shown = _shown(tmp_path, capsys, LIMITS)
    # The entry with a site on the constant, then the one whose why names it; the rule's own line is its header.
    lines = shown('MAX_SHARE')
    assert lines[:3] == ['RULE MAX_SHARE: largest share', SHARE, PREVIEW] and lines[3] == 'source: rule.max-share', lines
    # The entry whose finding names the agreement and the flow anchored on it; the copies are the view's anchor lines,
    # not listed again.
    lines = shown('FEE')
    assert lines[:3] == ['RULE FEE: late fee', FEE_COPIES, 'rule INVOICE: flow'] and not [
        line for line in lines if line.startswith('same FEE')], lines
    assert shown('late_fee')[:6] == ['show late_fee', FEE_COPIES, INVOICE, 'rule FEE: late fee', 'rule INVOICE: flow',
                                     'same FEE app/fees.py:2']
    # A flow's view begins after its header with the entries of its anchor and the one whose finding names it, its own
    # line left out.
    lines = shown('INVOICE')
    assert lines[:5] == ['FLOW INVOICE', FEE_COPIES, INVOICE, 'source: assumed: an invoice charges the late fee',
                         'tests/intent/policies.py:15'] and lines[5].startswith('anchor FEE -> ') and \
        'rule INVOICE: flow' not in lines, lines
    # A states rule is listed by its home `module:Class.field`, read as its file's site, once and without the word
    # look-alike's trailing space.
    lines = shown('Hire.status')
    assert lines[:2] == ['show Hire.status', STATES] and lines.count(STATES) == 1 and STATES + ' ' not in lines, lines
    assert shown('app/decision.py')[:3] == ['show app/decision.py', STATES, 'module app/decision.py: 1 file, 1 function']
    for query in ('app', 'app/', './app'):
        assert shown(query)[:11] == [f'show {query}', SHARE, FEE_COPIES, PREVIEW, INVOICE,
                                     'rule FEE: late fee', STATES, 'rule INVOICE: flow', 'same FEE app/fees.py:2',
                                     'same FEE app/fees.py:7', 'module app/: 4 files, 4 functions'], query
    # A file at the repository's root is a PATH query too.
    (tmp_path / 'fees.py').write_text('# flowguard: same FEE\ndef old_fee(days):\n    return 2 * days\n', encoding='utf-8')
    assert shown('fees.py')[:5] == ['show fees.py', 'rule FEE: late fee', 'rule INVOICE: flow', 'same FEE fees.py:2',
                                    'module fees.py: 1 file, 1 function']


def test_a_why_or_ask_names_only_what_the_production_code_declares_in_that_case(tmp_path, capsys):
    # Planning Tool's tests declare SAP, EMPLOYEE_ID and ROUTE: `show SAP` listed the renumbering entry (its why says
    # "awaits the SAP renumbering"), `show EMPLOYEE_ID` the unique-key entry ("employee_id") and `show ROUTE` the
    # project-request entry ("No route approves"), each first, without saying it came from the text.
    known = CAPACITY['.flowguard/known.toml'].replace(
        'why   = "employeeService.update hands the employee it loaded before the renumbering to the home-unit change"',
        'why   = "employeeService.update awaits the SAP renumbering and then hands the employee it loaded before the '
        'renumbering to the home-unit change"') + '''
        [known.member-key]
        sites = ["backend/src/services/employee-utilization.service.ts:updateAssignmentPsp"]
        why   = "The unique key of project_members (project_id, employee_id, role) does not include status"
        act   = "leave"
    '''
    files = dict(CAPACITY, **{'.flowguard/known.toml': known, 'backend/tests/unit/report.test.ts': (
        "const SAP = 'S-1';\nconst EMPLOYEE_ID = 'e-1';\nconst ROUTE = '/api/x';\n\n"
        "test('report', () => {\n  expect([SAP, EMPLOYEE_ID, ROUTE]).toHaveLength(3);\n});\n")})
    _, shown = _shown(tmp_path, capsys, files)
    for query in ('SAP', 'EMPLOYEE_ID', 'ROUTE'):
        lines = shown(query)
        assert lines[0] == f'show {query}' and not [line for line in lines if line.startswith('known.')], lines
    # A constant the production code declares is matched as it is spelled, and only so.
    _commit(tmp_path, {'backend/src/config/keys.ts': "export const SAP = 'SAP';\nexport const EMPLOYEE_ID = 'employee_id';\n"})
    lines = shown('SAP')
    assert lines[2].startswith('known.renumber-order: left as it is: employeeService.update awaits the SAP renumbering'), lines
    for query in ('EMPLOYEE_ID', 'sap', 'ROUTE'):
        assert not [line for line in shown(query) if line.startswith('known.')], query


def test_show_of_a_field_site_as_known_toml_writes_it_lists_what_the_field_s_own_query_lists(tmp_path, capsys):
    # On Planning Tool `show backend/prisma/schema.prisma:PspElement.hierarchyLevel` printed the field's facts without
    # the together agreement on it, and `show backend/prisma/schema.prisma:CapacityCalendarEntry.value` no percent-scale
    # line, while `show PspElement.hierarchyLevel` and `show CapacityCalendarEntry.value` printed them.
    _, shown = _shown(tmp_path, capsys, AGREEMENTS)
    for field, agreement in (('PspElement.hierarchyLevel', PSP), ('Employee.organizationalUnitId', HOME)):
        query = f'backend/prisma/schema.prisma:{field}'
        lines = shown(query)
        assert lines[:3] == [f'show {query}', AGREED_NOTICE, agreement], lines
        assert lines[3].startswith(f'declared {field}: '), lines
    # The pair the agreement holds is no candidate here either.
    lines = shown('backend/prisma/schema.prisma:PspElement.hierarchyLevel')
    assert not [line for line in lines if line.startswith('together candidate') and 'PspElement.parentPspId' in line], lines
    _, shown = _shown(tmp_path / 'capacity', capsys, CAPACITY)
    query = 'backend/prisma/schema.prisma:CapacityCalendarEntry.value'
    assert shown(query)[:4] == [f'show {query}', NOTICE, IGNORE, ASKED]


# Planning Tool's `together Project.leaderId ProjectMember.*` sits right above assignProjectManager; projectService.create
# sets a project's leader without a membership, and pspElementService.move changes the parent but not the level.
MEMBERS = dict(AGREEMENTS, **{
    'backend/prisma/schema.prisma': AGREEMENTS['backend/prisma/schema.prisma'].replace(
        '          lifecycleStatusId String @map("lifecycle_status_id")\n',
        '          lifecycleStatusId String @map("lifecycle_status_id")\n          leaderId          String? @map("leader_id")\n')
    + '''
        model ProjectMember {
          id         String @id
          projectId  String @map("project_id")
          employeeId String @map("employee_id")
          role       String
          @@map("project_members")
        }
    ''',
    'backend/src/services/project.service.ts': AGREEMENTS['backend/src/services/project.service.ts'].replace(
        'async create(name: string, lifecycleStatusId: string) {\n            return prisma.project.create({ data: { name, lifecycleStatusId } });',
        'async create(name: string, lifecycleStatusId: string, leaderId: string) {\n'
        '            return prisma.project.create({ data: { name, lifecycleStatusId, leaderId } });'),
    'backend/src/services/project-member.service.ts': '''
        import { prisma } from '../lib/prisma';

        // flowguard: together Project.leaderId ProjectMember.*
        export async function assignProjectManager(projectId: string, employeeId: string) {
          await prisma.project.update({ where: { id: projectId }, data: { leaderId: employeeId } });
          return prisma.projectMember.create({ data: { projectId, employeeId, role: 'PM' } });
        }
    ''',
    'backend/src/services/psp-element.service.ts': AGREEMENTS['backend/src/services/psp-element.service.ts'].replace(
        'data: { title, parentPspId, hierarchyLevel } });\n          },\n        };',
        'data: { title, parentPspId } });\n          },\n        };'),
})
LEADER = 'together Project.leaderId ProjectMember.* backend/src/services/project-member.service.ts:3'
MEMBERS_NOTICE = AGREED_NOTICE.replace('typescript 5/5', 'typescript 6/6')


def test_an_agreement_on_every_field_of_a_model_concerns_its_table_and_columns_too(tmp_path, capsys):
    # On Planning Tool `show ProjectMember` listed the together line; `show project_members` and
    # `show project_members.employee_id` printed none.
    _, shown = _shown(tmp_path, capsys, MEMBERS)
    for query in ('ProjectMember', 'ProjectMember.employeeId', 'project_members', 'project_members.employee_id',
                  'projects.leader_id'):
        assert shown(query)[1:3] == [MEMBERS_NOTICE, LEADER], query
    assert LEADER not in shown('Employee.organizationalUnitId')


def test_show_of_a_function_or_file_lists_the_last_run_s_lines_placed_there(tmp_path, capsys):
    # On Planning Tool the block called together Project.leaderId at projectService.create and together
    # PspElement.parentPspId at move broken at task start; `show projectService.create`, its map node and `show move`
    # did not say so.
    cfg, shown = _shown(tmp_path, capsys, MEMBERS)
    node = 'typescript/backend/src/services/project.service.ts:create'
    assert not [line for line in shown(node) if '(last run)' in line]          # no run recorded yet
    assert cli.static_check(cfg, everything=True) == 0
    block = capsys.readouterr().out.splitlines()
    leader = ('before (last run): together Project.leaderId at backend/src/services/project.service.ts:create was broken '
              'at task start -> leave it unless your task is about it')
    move = ('before (last run): together PspElement.parentPspId at backend/src/services/psp-element.service.ts:move was '
            'broken at task start -> leave it unless your task is about it')
    assert leader.replace(' (last run)', '').replace('backend/src/services/', '') in block, block
    # After the agreements, one line each with its kind: the node, the object.method, the bare name and the file.
    lines = shown(node)
    assert lines[lines.index(MEMBERS_NOTICE) + 1:lines.index(MEMBERS_NOTICE) + 3] == [WRITERS, leader], lines
    for query in ('projectService.create', 'backend/src/services/project.service.ts'):
        assert leader in shown(query), query
    lines = shown('move')
    assert lines[:3] == ['show move', MEMBERS_NOTICE, move], lines
    assert leader not in shown('pspElementService.create') and move not in shown('update')
    # A folder lists none: the agreements written there, not every old finding under it.
    assert not [line for line in shown('backend/src/services') if '(last run)' in line]


def test_a_site_query_whose_symbol_names_no_function_there_lists_only_what_is_at_that_file(tmp_path, capsys):
    # K2-0 (2026-11): on Planning Tool `show backend/src/services/absence.service.ts:create` (the method there is
    # absenceService.create) and `show backend/prisma/schema.prisma:create` began with the writers agreement of
    # project.service.ts, the together agreement of psp-element.service.ts and the last run's findings at
    # project.service.ts:create: the bare symbol's matches in other files, none of them at the queried file.
    files = dict(MEMBERS, **{'backend/src/services/absence.service.ts': '''
        import { prisma } from '../lib/prisma';

        export const absenceService = {
          async create(title: string) {
            return prisma.project.findMany({ where: { name: title } });
          },
        };
    '''})
    cfg, shown = _shown(tmp_path, capsys, files)
    notice = MEMBERS_NOTICE.replace('typescript 6/6', 'typescript 7/7')
    assert cli.static_check(cfg, everything=True) == 0
    capsys.readouterr()
    leader = ('before (last run): together Project.leaderId at backend/src/services/project.service.ts:create was broken '
              'at task start -> leave it unless your task is about it')
    for query in ('backend/src/services/absence.service.ts:create', 'backend/prisma/schema.prisma:create'):
        lines = shown(query)
        assert lines[:2] == [f'show {query}', notice], lines
        assert not [line for line in lines if line.startswith(('writers ', 'together ', 'before ', 'known.'))], lines
    # In the file that holds the function, its agreement and its last run's lines are still listed.
    lines = shown('backend/src/services/project.service.ts:create')
    assert lines[2:4] == [WRITERS + ' (site backend/src/services/project.service.ts:projectService.create)', leader], lines
    assert PSP not in '\n'.join(lines)


def test_a_site_query_lists_the_agreements_written_in_its_file_that_name_its_symbol(tmp_path, capsys):
    # Z-0 (2026-11): after K2-0, Planning Tool's `show backend/src/services/project-member.service.ts:Project.leaderId`
    # no longer listed `together Project.leaderId ProjectMember.*` written in that file (nor demand.service.ts's together
    # Demand.projectId line, nor sap-number-renumber.service.ts's), and `show backend/src/utils/calendar-iso.ts:
    # ISO_WEEKS_IN_YEAR` dropped known.iso-weeks and the `same ISO_WEEKS_IN_YEAR` copies whose comment sits there: the
    # file declares neither symbol, so every name written without a file was left out, those of its own comments too.
    _, shown = _shown(tmp_path, capsys, MEMBERS)
    for query, agreement in (('backend/src/services/project-member.service.ts:Project.leaderId', LEADER),
                             ('backend/src/services/project-member.service.ts:ProjectMember.role', LEADER),
                             ('backend/src/services/psp-element.service.ts:PspElement.hierarchyLevel', PSP),
                             ('backend/src/services/employee-home-unit.service.ts:Employee.organizationalUnitId', HOME)):
        lines = shown(query)
        assert lines[:3] == [f'show {query}', MEMBERS_NOTICE, agreement], lines
    # An agreement written in another file is not at this file and symbol (K2-0 holds).
    lines = shown('backend/src/services/project.service.ts:Project.leaderId')
    assert not [line for line in lines if line.startswith(('together ', 'writers '))], lines
    assert PSP not in shown('backend/src/services/psp-element.service.ts:Project.leaderId')
    # A `same NAME` agreement with a copy in the file: each copy's line, the rule anchored on it and the known entry
    # whose finding names it with a site there; the file that holds no copy lists none of them.
    _, shown = _shown(tmp_path / 'capacity', capsys, CAPACITY)
    query = 'backend/src/utils/calendar-iso.ts:ISO_WEEKS_IN_YEAR'
    lines = shown(query)
    assert lines[:7] == [f'show {query}', NOTICE, LEAVE, RULE, CITED, SAME,
                         'same ISO_WEEKS_IN_YEAR frontend/src/utils/weeks.ts:2'], lines
    lines = shown('backend/src/services/capacity.service.ts:ISO_WEEKS_IN_YEAR')
    assert not {LEAVE, RULE, CITED, SAME} & set(lines) and not [line for line in lines if line.startswith('same ')], lines


def test_a_rule_s_view_lists_the_entries_of_its_anchors_and_a_class_lists_its_methods_entries(tmp_path, capsys):
    # A rule whose id differs from its anchor (ISO_WEEKS on ISO_WEEKS_IN_YEAR) listed none of the anchor's entries.
    _, shown = _shown(tmp_path, capsys, CAPACITY)
    lines = shown('ISO_WEEKS')
    assert lines[:3] == ['RULE ISO_WEEKS: iso weeks in a year', NOTICE, LEAVE], lines
    # A Python class's map node lists the entries with a site on its methods.
    files = dict(LIMITS, **{'.flowguard/known.toml': LIMITS['.flowguard/known.toml'] + '''
        [known.hire-hold]
        sites = ["app/decision.py:Hire.hold"]
        why   = "A hold keeps the hire open until it is returned"
        act   = "leave"
    '''})
    _, shown = _shown(tmp_path / 'limits', capsys, files)
    hold = ('known.hire-hold: left as it is: A hold keeps the hire open until it is returned '
            '(python -m flowguard show known.hire-hold)')
    lines = shown('app.decision:Hire')
    assert lines[:2] == ['show app.decision:Hire', hold] and any(     # what concerns it, then its node view (gate-4)
        line.startswith('app.decision:Hire app/decision.py:1') for line in lines[2:]), lines
    assert hold not in shown('app.limits:share_ok')


ROLES = ('known.roles: asked the owner on 2026-11-15, no answer yet: Are the four admin roles of docs/notes/admin_roles.md '
         'planned work, or dropped? (python -m flowguard show known.roles)')


def test_a_document_or_a_path_the_map_does_not_read_says_what_it_is_and_lists_the_entries_naming_it(tmp_path, capsys):
    # On Planning Tool `show docs/notes/admin_roles.md` printed `module docs/notes/admin_roles.md: 1 file, 0 functions`
    # only, although known.roles asks about that document, and `show pyproject.toml` told the agent to put an about
    # marker above the text that is its contract.
    files = dict(CAPACITY, **{
        'docs/notes/admin_roles.md': '# Admin roles\n\nHR Admin, Controlling Admin, Project Planning Admin, Self-Planning.\n',
        'frontend/src/types/permissions.ts': "export const APPLICATION_ROLES = ['SYSTEM_ADMIN', 'MANAGEMENT'] as const;\n",
        'docker-compose.yml': 'services:\n  db:\n    image: postgres\n',
        '.flowguard/known.toml': CAPACITY['.flowguard/known.toml'] + '''
        [known.roles]
        sites = ["frontend/src/types/permissions.ts:APPLICATION_ROLES"]
        why   = "The requirements list the roles R1 to R10; docs/notes/admin_roles.md, added later, names HR Admin, Controlling Admin, Project Planning Admin and Self-Planning, which the code's role lists do not have"
        act   = "ask"
        asked = "2026-11-15"
        ask   = "Are the four admin roles of docs/notes/admin_roles.md planned work, or dropped?"
    '''})
    _, shown = _shown(tmp_path, capsys, files)
    def unmapped(query):            # the view without its Map line
        return [line for line in shown(query) if not line.startswith('Map: ')]
    assert unmapped('docs/notes/admin_roles.md') == ['show docs/notes/admin_roles.md', ROLES, 'document docs/notes/admin_roles.md']
    assert unmapped('docs/notes') == ['show docs/notes', ROLES,
                                      'folder docs/notes/: no source file the map reads; 1 Markdown document']
    assert ROLES not in shown('docs/requests.md')
    for path in ('pyproject.toml', 'docker-compose.yml'):
        assert unmapped(path) == [f'show {path}', f'{path}: no source file the map reads, and no Markdown document'], path
    # The repository's root holds every mapped file, and no about marker can name it.
    lines = shown('.')
    assert lines[0] == 'show .' and any(line.startswith('module ./: ') for line in lines) and ROLES in lines \
        and not [line for line in lines if 'about ./' in line], lines


def test_a_known_entry_s_bare_id_is_that_entry_and_words_find_the_entries_sharing_them(tmp_path, capsys):
    # On Planning Tool `show percent-scale`, `show "percent scale"` and `show "ISO weeks in a year"` printed no known line.
    cfg, shown = _shown(tmp_path, capsys, CAPACITY)
    assert cli.show(cfg, 'known.percent-scale') == 0
    whole = capsys.readouterr().out.splitlines()
    assert shown('percent-scale') == whole and whole[0] == 'known.percent-scale: act ask, asked on 2026-11-15', whole
    # an entry that shares a word is the first word match, after the line that says they only share a word
    assert shown('percent scale')[:4] == ['show percent scale', NOTICE,
                                          'word matches: the 2 lines below only share a word with percent scale', ASKED]
    # After the exact matches: here the intent rule that decides 'iso weeks in a year'.
    lines = shown('ISO weeks in a year')
    assert lines[:3] == ['show ISO weeks in a year', NOTICE, RULE + ' A year has 53 ISO weeks when its '
                         '28 December falls in week 53.'] and lines[3].startswith('word matches: the ') and lines[4] == LEAVE, lines
    # Words that no entry's why or ask holds list none.
    assert not [line for line in shown('widget colour') if line.startswith('known.')]


def test_the_repository_keeps_its_rules_in_force_each_quoting_stored_owner_words(capsys):
    from pathlib import Path
    root = Path(__file__).resolve().parents[2]
    cfg = load_config(root)
    found = sources.catalog(cfg)
    assert found.issues == [] and list(found.rules) == ['regression-role', 'current-rules', 'efficient-use', 'english-skill',
                                                        'chinese-conversation', 'no-harm', 'report-open-matters',
                                                        'upgrade-consent', 'offered-choice', 'session-finish-error']
    assert [found.rules[name].source.partition(' ')[0] for name in found.rules] == ['R68', 'R80', 'R75', 'R74', 'R58', 'R85',
                                                                                     'R95', 'R95', 'R105', 'R106']
    for rule in found.rules.values():
        assert rule.text.isascii() and sources.catalog_authority(sources.parse(rule.source, strict=True), cfg, None)[0], rule
    assert cli.show(cfg, 'rules') == 0
    lines = capsys.readouterr().out.splitlines()
    assert lines[0] == 'FlowGuard rules: 10 in .flowguard/rules.toml, 0 known in .flowguard/known.toml, 0 input problems'
    # the owner's pick of an option the agent offered holds as his pick, never as his words (R105)
    assert sum(line.startswith('rule.') for line in lines) == 10 and sum(line.endswith('(holds)') for line in lines) == 9
    assert sum(line.endswith("(holds: the agent's option, the owner's pick)") for line in lines) == 1, lines


FEES = {
    'fees.py': '''
        # flowguard: same FEE
        def late_fee(days: int) -> int:
            if days <= 3:
                return 0
            return (days - 3) * 2


        # flowguard: same FEE
        def preview_fee(days: int) -> int:
            if days <= 3:
                return 0
            return (days - 3) * 3
    ''',
    'tests/test_fees.py': '''
        from fees import late_fee, preview_fee

        def test_fee():
            assert late_fee(5) == 4
            assert preview_fee(2) == 0
    ''',
    '.flowguard/known.toml': '''
        [known.fee-copies]
        sites   = ["fees.py:late_fee", "fees.py:preview_fee"]
        why     = "The preview charges 3 per late day, the invoice 2"
        act     = "ask"
        ask     = "Which daily late fee is right, 2 or 3?"
        finding = "same:FEE"
    ''',
}


@pytest.mark.parametrize('old, new', [
    ('    return (days - 3) * ', '    late = days - 3\n    return late * '),         # both copies' code, not their answers
    ('        return 0\n', '        return 0  # on time\n'),                           # a comment in each copy
])
def test_copies_that_disagreed_at_task_start_are_the_known_entry_s_in_pytest_check_and_check_static_alike(tmp_path, old, new):
    """A known entry names the same-name disagreement the task started with, and the change touches both copies: each
    run says `known` with the entry's step and nothing red; check compares the copies at the task start too."""
    from tests.intent_engine.test_unverified_outcome import _cli, _project, _pytest
    from tests.intent_engine._cli_fixture import block
    root = _project(tmp_path / 'p', FEES)
    path = root / 'fees.py'
    path.write_text(path.read_text(encoding='utf-8').replace(old, new), encoding='utf-8')
    # The finding's two copies, then the entry's question (Planning Tool's known line gave neither its touched site nor
    # its question).
    known = ('known: known.fee-copies at fees.py:late_fee, fees.py:preview_fee: Which daily late fee is right, 2 or 3? '
             '-> an open question for the owner, not asked yet')
    for run, (result, _) in (('pytest', _pytest(root, '-q')), ('check', _cli(root, 'check')),
                             ('check --static', _cli(root, 'check', '--static'))):
        shown = block(result)
        assert result.returncode == 0 and ': 0 red, 1 known; ' in shown[0], (run, shown)
        assert shown[1:] == [known], (run, result.stdout)


# An invalid entry and one whose site names nothing: input findings, red in every run (D4).
BROKEN_KNOWN = '''
    [known.bad]
    sites = "x"

    [known.ghost]
    sites = ["src/app.py:nosuch"]
    why = "a site that names nothing"
    act = "leave"
'''
BROKEN_REDS = [
    'red: known.bad: missing why; missing act; sites is a non-empty list of path:symbol -> correct [known.bad] in known.toml',
    'red: known.ghost: site src/app.py:nosuch names nothing in src/app.py: name one function, object.method, constant or '
    'Model.field of that file -> correct the sites of [known.ghost] in known.toml']
PLAIN = {
    'src/__init__.py': '',
    'src/app.py': 'def fee(days):\n    return days * 2\n',
    'tests/test_app.py': 'from src.app import fee\n\n\ndef test_fee():\n    assert fee(1) == 2\n',
    'pyproject.toml': '[tool.pytest.ini_options]\npythonpath = ["."]\ntestpaths = ["tests"]\n'
                      'addopts = "-p flowguard.intent.plugin"\n',
    '.gitignore': '.flowguard/cache/\n__pycache__/\n',
    '.flowguard/known.toml': BROKEN_KNOWN,
}
NO_BASELINE = {'outside Git': 'no baseline: nothing compared', 'unborn branch': 'no baseline: nothing compared',
               'recorded start missing': 'since bbbbbbb, not in this repository: nothing compared; run python -m flowguard new-task'}


def _without_baseline(root, state):
    """`PLAIN` with no commit to compare with: in no repository, on a branch before its first commit, or with a
    recorded task start this repository lacks; or committed, with no source change since."""
    from flowguard.intent import cache
    _write(root, PLAIN)
    if state != 'outside Git':
        _git(root, 'init', '-q', '-b', 'main')
    if state in ('recorded start missing', 'no source change'):
        _commit(root)
    if state == 'recorded start missing':
        cache._record_baseline(load_config(root), 'b' * 40)
    return root


@pytest.mark.parametrize('state', list(NO_BASELINE))
def test_check_reports_an_invalid_or_unresolvable_known_entry_without_a_baseline_as_check_static_does(tmp_path, state):
    """With nothing to compare (no baseline), nothing is new, but an entry of known.toml that is invalid or names
    nothing is red in check too, also when it runs no pytest batch (no intent items), as in check --static (D4)."""
    from tests.intent_engine.test_unverified_outcome import _cli
    from tests.intent_engine._cli_fixture import block
    root = _without_baseline(tmp_path / 'p', state)
    for arguments in (('check',), ('check', '--static')):
        result, _ = _cli(root, *arguments)
        shown = block(result)
        assert result.returncode == 1 and shown[0].startswith(f'FlowGuard {signals.version()} ({NO_BASELINE[state]}): 2 red; '), (
            arguments, result.stdout + result.stderr)
        assert shown[1:] == BROKEN_REDS, (arguments, result.stdout)


@pytest.mark.parametrize('state', ['no source change', *NO_BASELINE])
def test_pytest_without_a_source_change_reports_a_known_site_that_names_nothing_as_check_does(tmp_path, state):
    """A pytest run whose map checks do not run (no source change, or no baseline) still resolves the known sites on
    the map: an entry whose site names nothing is red, as the invalid entry beside it, in check and check --static
    too (D4)."""
    from tests.intent_engine.test_unverified_outcome import _cli, _pytest
    from tests.intent_engine._cli_fixture import block
    root = _without_baseline(tmp_path / 'p', state)
    for run, (result, _) in (('pytest', _pytest(root, '-q')), ('check', _cli(root, 'check')),
                             ('check --static', _cli(root, 'check', '--static'))):
        shown = block(result)
        assert result.returncode == 1 and ': 2 red; ' in shown[0], (run, result.stdout + result.stderr)
        assert shown[1:] == BROKEN_REDS, (run, result.stdout)


def test_copies_that_agree_again_make_their_known_entry_known_fixed_in_pytest_and_check(tmp_path):
    """A real fix: the change makes the copies the entry names agree. pytest compares them sealed on its recorded
    inputs and check on every input it makes for them (which, not a proof, it says in a not compared line); both find
    them agreeing, so the entry may be fixed: `known fixed?`, never `known`. check --static compares no copies: the
    change touches one of the entry's sites, `known`, naming that site, how many the entry has and its question."""
    from tests.intent_engine.test_unverified_outcome import _cli, _project, _pytest
    from tests.intent_engine._cli_fixture import block
    root = _project(tmp_path / 'p', FEES)
    path = root / 'fees.py'
    path.write_text(path.read_text(encoding='utf-8').replace('(days - 3) * 3', '(days - 3) * 2'), encoding='utf-8')
    fixed = ('known fixed?: known.fee-copies: copies of FEE now agree -> the owner has not answered known.fee-copies: if this change '
             'settles it, say so in your report')
    for run, (result, _), expected in (
            ('pytest', _pytest(root, '-q'), [fixed]),
            ('check', _cli(root, 'check'), [fixed, 'not compared: FEE (returns, or numeric classes are not readable here: '
                                                   'compared on 9 representative values) -> not a failure'])):
        assert result.returncode == 0 and block(result)[1:] == expected, (run, result.stdout + result.stderr)
    result, _ = _cli(root, 'check', '--static')
    assert result.returncode == 0 and block(result)[1:] == [
        'known: known.fee-copies at fees.py:preview_fee (1 of 2 places): Which daily late fee is right, 2 or 3? -> an open '
        'question for the owner, not asked yet'], result.stdout
