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
    ('text = "x"\nsource = \'owner R1: w\'\n', "source 'owner R1: w' is neither R<id> \"exact words\" nor doc PATH \"exact words\""),
    ('text = "x"\nsource = \'R1 words\'\n', "source 'R1 words' is neither R<id> \"exact words\" nor doc PATH \"exact words\""),
    ('text = "x"\nsource = \'rule.other\'\n', "source rule.other cites another catalog entry: quote the owner's words or a document instead"),
    ('text = "x"\nsource = 1\n', 'source is a string R<id> "exact words" or doc PATH "exact words", not 1'),
])
def test_every_invalid_rule_entry_is_an_input_finding_and_counts_nothing(tmp_path, entry, problem):
    found = sources.catalog(_project(tmp_path, rules='[rule.x]\n' + entry + '\n[rule.ok]\ntext = "y"\nsource = \'R1 "w"\'\n', known=None))
    assert list(found.rules) == ['ok']
    assert problem in _problems(found, 'rules-entry:rule.x').split('; ')
    issue = next(issue for issue in found.issues if issue.name == 'rules-entry:rule.x')
    # the entry is the line's subject and place, named once: `red: rule.x: missing source -> ...`
    assert issue.parts[0][1] == ('.flowguard/rules.toml:rule.x',) and issue.subject == 'rule.x' and issue.files == {'.flowguard/rules.toml'}
    assert issue.rank == 0 and issue.new          # only the 4.3 lines report it: no structure count, listing or lead


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
    (BASE + "source = 'assumed: x'\n", "source 'assumed: x' is neither R<id> \"exact words\" nor doc PATH \"exact words\""),
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
        'known.roles at web/c.ts:APPLICATION_ROLES', 'known.grace at src/settings.py:defaults']


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
    step = "name it in your report; needs the owner's yes"
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


def test_the_repository_keeps_its_rules_in_force_each_quoting_stored_owner_words(capsys):
    from pathlib import Path
    root = Path(__file__).resolve().parents[2]
    cfg = load_config(root)
    found = sources.catalog(cfg)
    assert found.issues == [] and list(found.rules) == ['regression-role', 'current-rules', 'efficient-use', 'english-skill',
                                                        'chinese-conversation', 'no-harm']
    assert [found.rules[name].source.partition(' ')[0] for name in found.rules] == ['R68', 'R80', 'R75', 'R74', 'R58', 'R85']
    for rule in found.rules.values():
        assert rule.text.isascii() and sources.catalog_authority(sources.parse(rule.source, strict=True), cfg, None)[0], rule
    assert cli.show(cfg, 'rules') == 0
    lines = capsys.readouterr().out.splitlines()
    assert lines[0] == 'FlowGuard rules: 6 in .flowguard/rules.toml, 0 known in .flowguard/known.toml, 0 input problems'
    assert sum(line.startswith('rule.') for line in lines) == 6 and sum(line.endswith('(holds)') for line in lines) == 6


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
    known = 'known: known.fee-copies at fees.py:late_fee, fees.py:preview_fee -> ask owner (not asked yet)'
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
