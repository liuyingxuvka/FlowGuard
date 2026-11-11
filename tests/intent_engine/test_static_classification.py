"""The 4.3 classification of the static findings (stage 3, lane C): each finding names its family, subject and one
part per member, and the members this change added (`Issue.fresh`); `signals.deliver` turns them into lines.

The agreement a finding is judged by is the current one, applied to the baseline code too (D2): a member is new
only when the change's code added it. Structure findings are never red (D1): a new one is `impact`, an old one in a
function or file the change touches is `before`. Each fixture commits its baseline and edits the working tree.
"""
from contextlib import closing

from flowguard.intent import anchors, owners, signals
from flowguard.intent.config import load_config
from flowguard.structure import build
from tests.intent_engine.test_static_check import _commit, _write


def _found(root, *, everything=False, replay=False):
    cfg = load_config(root)
    with closing(build(root, roots=cfg.roots)) as graph:
        return owners.static_findings(cfg, graph, anchors.collect(graph), 'HEAD', everything=everything, replay=replay)


def _deliver(found, *, everything=False, known=()):
    lines, _ = signals.deliver(found.issues, touched_functions=found.touched_functions, touched_files=found.touched_files,
                               known=known, ran=found.ran, everything=everything, extra=found.lines)
    return lines


def _issue(found, name):
    return next(issue for issue in found.issues if issue.name == name)


def _module(root, file):
    cfg = load_config(root)
    with closing(build(root, roots=cfg.roots)) as graph:
        return graph.con.execute('SELECT module FROM file WHERE path = ?', (file,)).fetchone()[0]


def _kinds(lines, name):
    return sorted((line.kind, line.function.partition(':')[2]) for line in lines if line.name == name)


SCHEMA = 'model Item {\n  id    String @id\n  state String\n  note  String\n}\n'


def _write_state(function, value='x', field='state', comment=''):
    return comment + f"""export async function {function}(prisma: any) {{
  await prisma.item.update({{ where: {{ id: '1' }}, data: {{ {field}: '{value}' }} }});
}}
"""


# ---- writer: writes outside a writers agreement ----------------------------------------------------------

def test_a_write_outside_a_writers_agreement_is_red_only_when_this_change_adds_it(tmp_path):
    agreement = '// flowguard: writers Item.state setState\n'
    _commit(tmp_path, {'prisma/schema.prisma': SCHEMA, 'app/owner.ts': _write_state('setState', comment=agreement),
                       'app/legacy.ts': _write_state('legacy'), 'app/still.ts': _write_state('stillOld')})
    _write(tmp_path, {'app/legacy.ts': _write_state('legacy', 'y'), 'app/rogue.ts': _write_state('rogue')})
    found = _found(tmp_path)
    issue = _issue(found, 'writer:Item.state')
    rogue = _module(tmp_path, 'app/rogue.ts') + ':rogue'
    assert (issue.family, issue.subject, issue.fresh) == ('writer', 'writers Item.state', frozenset({rogue}))
    assert [part[1:] for part in issue.parts] == [
        ('app/legacy.ts:legacy', 'writes Item.state outside setState', 'call setState instead'),
        ('app/rogue.ts:rogue', 'writes Item.state outside setState', 'call setState instead'),
        ('app/still.ts:stillOld', 'writes Item.state outside setState', 'call setState instead')]
    lines = _deliver(found)
    assert _kinds(lines, 'writer:Item.state') == [('before', 'legacy'), ('red', 'rogue')]
    red = next(line for line in lines if line.kind == 'red')
    assert (red.text, red.step, red.places) == ('writers Item.state: app/rogue.ts:rogue writes Item.state outside setState',
                                                'call setState instead', ('app/rogue.ts:rogue',))
    assert 'except=' not in red.step and 'writers agreement' not in red.step      # no way to silence it on a red line
    # --all lists every old member as before.
    assert _kinds(_deliver(_found(tmp_path, everything=True), everything=True), 'writer:Item.state') == [
        ('before', 'legacy'), ('before', 'stillOld'), ('red', 'rogue')]


def test_a_writers_agreement_added_over_old_writes_leaves_them_before_not_red(tmp_path):
    # D2: the registration is the current one, applied to the baseline code: the old write was outside it then too.
    _commit(tmp_path, {'prisma/schema.prisma': SCHEMA, 'app/owner.ts': _write_state('setState'), 'app/legacy.ts': _write_state('legacy')})
    _write(tmp_path, {'app/owner.ts': _write_state('setState', comment='// flowguard: writers Item.state setState\n'),
                      'app/legacy.ts': _write_state('legacy', 'y')})
    found = _found(tmp_path)
    issue = _issue(found, 'writer:Item.state')
    assert issue.fresh == frozenset() and not issue.new
    assert _kinds(_deliver(found), 'writer:Item.state') == [('before', 'legacy')]
    assert not found.red                    # 4.2.1 counted the same old write as old: the legacy red agrees


# ---- values: a value written outside its declared set ------------------------------------------------------

STATE_ENUM = 'enum State {\n  open\n  shut\n%s}\n\nmodel Item {\n  id    String @id\n  state State\n}\n'


def test_a_value_made_outside_its_set_by_a_changed_constant_is_red_in_the_unchanged_function_that_writes_it(tmp_path):
    _commit(tmp_path, {'prisma/schema.prisma': STATE_ENUM % '',
                       'app/states.ts': "export const S = { A: 'open', B: 'shut' } as const;\n",
                       'app/b.ts': "import { S } from './states';\n" + _write_state('setState', 'open').replace("'open'", 'S.A')
                                   + _write_state('oldBad', 'gone')})
    _write(tmp_path, {'app/states.ts': "export const S = { A: 'opened', B: 'shut' } as const;\n",
                      'app/c.ts': _write_state('newBad', 'nope')})
    found = _found(tmp_path)
    issue = _issue(found, 'values:Item.state')
    module_b, module_c = _module(tmp_path, 'app/b.ts'), _module(tmp_path, 'app/c.ts')
    assert (issue.family, issue.subject) == ('values', 'values Item.state')
    # app/b.ts is unchanged: the baseline code, read with the baseline's constant, wrote 'open' there.
    assert issue.fresh == frozenset({module_b + ':setState', module_c + ':newBad'})
    assert sorted(part[1:3] for part in issue.parts) == [
        ('app/b.ts:oldBad', "writes 'gone' outside 'open'|'shut'"), ('app/b.ts:setState', "writes 'opened' outside 'open'|'shut'"),
        ('app/c.ts:newBad', "writes 'nope' outside 'open'|'shut'")]
    lines = _deliver(found)
    assert _kinds(lines, 'values:Item.state') == [('red', 'newBad'), ('red', 'setState')]       # oldBad: untouched, old
    assert all(line.step == 'use a declared value' for line in lines if line.name == 'values:Item.state')


def test_a_set_this_change_narrows_over_old_writes_leaves_them_before(tmp_path):
    # D2: the declared set is the registration; the old write was outside the narrowed set in the baseline code too.
    # 4.2.1 made it red (the declaration changed); 4.3 says before (a sanctioned 1 -> 0).
    old = _write_state('oldWrite', 'gone')
    _commit(tmp_path, {'prisma/schema.prisma': STATE_ENUM % '  gone\n', 'app/b.ts': old})
    _write(tmp_path, {'prisma/schema.prisma': STATE_ENUM % '', 'app/b.ts': old + 'export const touched = 1;\n'})
    found = _found(tmp_path)
    issue = _issue(found, 'values:Item.state')
    assert issue.fresh == frozenset() and issue.new           # `new` is the legacy flag the 4.2.1 red line kept
    assert any("app/b.ts:2 Item.state='gone'" in line for line in found.red)
    lines = _deliver(found)
    assert _kinds(lines, 'values:Item.state') == []              # oldWrite itself is untouched
    edited = _write_state('oldWrite', 'gone').replace("id: '1'", "id: '2'")
    _write(tmp_path, {'app/b.ts': edited})
    assert _kinds(_deliver(_found(tmp_path)), 'values:Item.state') == [('before', 'oldWrite')]


# ---- structure families: never red; new is impact, old touched is before (D1) -------------------------------

PARENTS = '''
model Parent {
  id       String  @id
  children Child[]
}

model Child {
  id       String @id
  parentId String
  parent   Parent @relation(fields: [parentId], references: [id], onDelete: Restrict)
}

model Ghost {
  id String @id
}
'''
REMOVE = '''export async function addChild(prisma: any, parentId: string) {
  await prisma.child.create({ data: { parentId } });
}
export async function removeOld(prisma: any, id: string) {
  await prisma.parent.delete({ where: { id: %s } });
}
export async function readGhost(prisma: any) {
  return prisma.ghost.findMany({ where: { id: '1' } });
}
'''


def test_a_new_delete_or_use_of_an_uncreated_table_is_impact_and_an_old_one_in_a_touched_function_is_before(tmp_path):
    _commit(tmp_path, {'prisma/schema.prisma': PARENTS, 'app/remove.ts': REMOVE % 'id'})
    _write(tmp_path, {'app/remove.ts': REMOVE % "id + ''", 'app/purge.ts': '''
        export async function removeNew(prisma: any, id: string) {
          await prisma.parent.delete({ where: { id } });
        }
        export async function readGhostNew(prisma: any) {
          return prisma.ghost.findFirst({ where: { id: '2' } });
        }
    '''})
    found = _found(tmp_path)
    remove, purge = _module(tmp_path, 'app/remove.ts'), _module(tmp_path, 'app/purge.ts')
    old, new = _issue(found, 'delete:app/remove.ts:removeOld:Parent'), _issue(found, 'delete:app/purge.ts:removeNew:Parent')
    assert (old.family, old.subject, old.fresh) == ('delete', 'delete Parent', frozenset())
    assert new.fresh == frozenset({purge + ':removeNew'}) and new.parts[0][1] == 'app/purge.ts:removeNew'
    assert new.parts[0][2].startswith('deletes Parent; Restrict child tables Child are not deleted, cleared or counted')
    ghost = _issue(found, 'uncreated:Ghost')
    assert (ghost.family, ghost.subject, ghost.fresh) == ('uncreated', 'uncreated Ghost', frozenset({purge + ':readGhostNew'}))
    assert sorted(part[1:3] for part in ghost.parts) == [
        ('app/purge.ts:readGhostNew', 'reads Ghost, whose rows no code creates'),
        ('app/remove.ts:readGhost', 'reads Ghost, whose rows no code creates')]
    lines = _deliver(found)
    assert _kinds(lines, old.name) == [('before', 'removeOld')] and _kinds(lines, new.name) == [('impact', 'removeNew')]
    assert _kinds(lines, 'uncreated:Ghost') == [('impact', 'readGhostNew')]        # readGhost is old and untouched
    assert not [line for line in lines if line.kind == 'red']
    impact = next(line for line in lines if line.name == new.name)
    assert impact.step == signals.IMPACT_STEP and impact.text.startswith('delete Parent: app/purge.ts:removeNew deletes Parent')
    before = next(line for line in lines if line.name == old.name)
    assert before.text == 'delete Parent at app/remove.ts:removeOld was broken at task start'
    assert remove + ':removeOld' in found.touched_functions and 'app/remove.ts' in found.touched_files
    assert {'delete', 'uncreated', 'writers', 'values', 'columns', 'ondelete', 'labels', 'copies', 'declarations',
            'writer', 'pair'} <= found.ran


def test_fields_several_files_write_without_an_agreement_have_lines_only_with_all(tmp_path):
    files = {f'app/{name}.ts': _write_state(name, field='note') for name in ('first', 'second', 'third')}
    _commit(tmp_path, {'prisma/schema.prisma': SCHEMA, **files})
    _write(tmp_path, {'app/fourth.ts': _write_state('fourth', field='note'), 'app/first.ts': _write_state('first', 'y', field='note')})
    found = _found(tmp_path)
    issue = _issue(found, 'writers:Item.note')
    assert (issue.family, issue.subject) == ('writers', 'no writers agreement for Item.note')
    assert issue.fresh == frozenset({_module(tmp_path, 'app/fourth.ts') + ':fourth'})
    assert _kinds(_deliver(found), issue.name) == []           # merged into the impact line of a changed function
    assert _kinds(_deliver(_found(tmp_path, everything=True), everything=True), issue.name) == [
        ('before', 'first'), ('before', 'second'), ('before', 'third'), ('impact', 'fourth')]


def test_declarations_that_already_differed_are_before_in_a_touched_file_and_new_ones_are_impact(tmp_path):
    _commit(tmp_path, {'app/a.ts': "export type Kind = 'a' | 'b';\n", 'app/b.ts': "export type Kind = 'a' | 'b' | 'c';\n",
                       'app/c.ts': "export type Tone = 'x' | 'y';\n", 'app/d.ts': "export type Tone = 'x' | 'y';\n"})
    _write(tmp_path, {'app/b.ts': "export type Kind = 'a' | 'b' | 'c';\nexport function more() { return 1; }\n",
                      'app/d.ts': "export type Tone = 'x' | 'z';\n"})
    found = _found(tmp_path)
    kind, tone = _issue(found, 'declarations:Kind'), _issue(found, 'declarations:Tone')
    assert (kind.family, kind.subject, kind.fresh) == ('declarations', 'declarations Kind', frozenset())
    assert kind.parts == (('', 'app/a.ts:1', "declares 'a' | 'b'; app/b.ts:1 declares 'a' | 'b' | 'c'",
                           'keep one definition and reference it elsewhere; use different names if intentionally different'),)
    assert tone.fresh == frozenset({''}) and tone.files == frozenset({'app/c.ts', 'app/d.ts'})
    lines = _deliver(found)
    assert [(line.kind, line.text) for line in lines if line.name in (kind.name, tone.name)] == [
        ('before', 'declarations Kind at app/a.ts:1 was broken at task start'),
        ('impact', "declarations Tone: app/c.ts:1 declares 'x' | 'y'; app/d.ts:1 declares 'x' | 'z'")]


# ---- [structure] decisions, the deprecated heuristics, changed-alone --------------------------------------

DECISION = '''
[structure."uncreated:Ghost"]
decision = "The owner said these rows come from the nightly import job"
source = { file = "docs/owner.md", text = "Ghost rows come from the nightly import." }

[structure."writers:Item.state"]
decision = "The owner said only the service may write this state field"
source = { file = "docs/owner.md", text = "Ghost rows come from the nightly import." }
'''


def test_a_structure_decision_closes_its_finding_and_one_without_its_anchor_is_an_input_red(tmp_path, capsys):
    _commit(tmp_path, {'prisma/schema.prisma': PARENTS + SCHEMA, 'app/remove.ts': REMOVE % 'id',
                       'docs/owner.md': 'Ghost rows come from the nightly import.\n', '.flowguard/ledger.toml': DECISION})
    _write(tmp_path, {'app/remove.ts': REMOVE % "id + ''"})
    found = _found(tmp_path)
    assert 'uncreated:Ghost' in found.decided and not [issue for issue in found.issues if issue.name == 'uncreated:Ghost']
    wrong = _issue(found, 'structure-decision:writers:Item.state')
    assert (wrong.family, wrong.fresh, wrong.parts[0][1]) == ('input', frozenset({''}), '.flowguard/ledger.toml:[structure."writers:Item.state"]')
    assert _kinds(_deliver(found), wrong.name) == [('red', '')]
    # The section is deprecated and names its replacement (design 6.2).
    assert ('deprecated: ledger [structure] will be removed in 5.0; write [known.<id>] in .flowguard/known.toml '
            'with act = "ignore" or "leave"') in capsys.readouterr().err.splitlines()


def test_label_spelling_leads_get_no_line_and_are_kept_for_show_last(tmp_path):
    _commit(tmp_path, {'app/a.ts': "export function a(x: string) { return x === 'Open Case' ? 1 : 2; }\n"})
    _write(tmp_path, {'app/b.ts': "export function b(x: string) { return x === 'open case' ? 1 : 2; }\n"})
    found = _found(tmp_path)
    hidden = [item for item in found.hidden if item['feature'] == 'label-spelling leads']
    assert len(hidden) == 1 and "'open case'(app/b.ts:1, spelling added in this task)" in hidden[0]['text'], found.hidden
    assert all(ord(character) < 128 for item in found.hidden for character in item['text'])
    assert not [issue for issue in found.issues if 'label' in issue.family] and not found.lines


LIMITS = '''# flowguard: owner LIMIT
def chart(days: int) -> bool:
    return days <= 3


# flowguard: sensor LIMIT
def report(days: int) -> bool:
    return days <= %d
'''


def test_a_registered_copy_changed_alone_is_a_red_finding_and_what_cannot_be_compared_is_a_not_compared_line(tmp_path):
    raising = 'def %s(value: int):\n    raise ValueError("same")\n'
    _commit(tmp_path, {'limits.py': LIMITS % 3, 'pyproject.toml': '[tool.pytest.ini_options]\npythonpath=["."]\n',
                       'policy.py': raising % 'limit', 'peer.py': raising % 'copy'})
    _write(tmp_path, {'limits.py': LIMITS % 4, 'policy.py': raising % 'limit' + '    return value\n'})
    cfg = load_config(tmp_path)
    with closing(build(tmp_path, roots=cfg.roots)) as graph:
        found = owners.changed_alone(cfg, graph, anchors.collect(graph), owners.Change(cfg, graph, 'HEAD'))
    issue = _issue(found, 'changed-alone:LIMIT')
    assert (issue.family, issue.subject, issue.fresh) == ('changed-alone', 'same LIMIT', frozenset({'limits:report'}))
    assert issue.parts == (('limits:report', 'limits.py:report',
                            'changed behavior; 1 copies that answered the same are unchanged: limits.py:chart',
                            'make report match reference chart(limits.py:2)'),)
    assert 'changed-alone' not in found.ran          # it judges only what the change edits: never `known fixed?`
    lines, _ = signals.deliver(found.issues, touched_functions=(), touched_files=(), extra=found.lines)
    assert [(line.kind, line.name) for line in lines] == [('red', 'changed-alone:LIMIT'), ('not compared', 'not compared:policy:limit')]
    assert lines[1].text.startswith('policy.py:limit (') and 'same raised exception' in lines[1].text
    assert lines[1].step == 'not a failure'


# ---- the --all listing, the baseline of typed members and declarations, known fixed?, one read ----------

GHOST = 'model Ghost {\n  id String @id\n}\n'


def test_the_all_listing_counts_and_lists_only_the_findings_it_shows(tmp_path):
    # Writes outside a writers agreement and declarations that differ are findings only the 4.3 lines report: the
    # --all listing neither counts nor lists them, as before they existed.
    agreement = '// flowguard: writers Item.state setState\n'
    _commit(tmp_path, {'prisma/schema.prisma': SCHEMA, 'app/a.ts': "export type Kind = 'a' | 'b';\n",
                       'app/b.ts': "export type Kind = 'a' | 'b' | 'c';\n",
                       'app/owner.ts': _write_state('setState', comment=agreement), 'app/legacy.ts': _write_state('legacy')})
    _write(tmp_path, {'app/legacy.ts': _write_state('legacy', 'y')})
    found = _found(tmp_path, everything=True)
    assert {'writer:Item.state', 'declarations:Kind'} <= {issue.name for issue in found.issues}
    assert not [line for line in found.section if 'structure issues' in line], found.section
    # With a listed problem beside them, the header counts the entries it lists.
    _write(tmp_path, {'prisma/schema.prisma': SCHEMA + GHOST,
                      'app/ghost.ts': "export async function readGhost(prisma: any) { return prisma.ghost.findMany({ where: { id: '1' } }); }\n"})
    cfg = load_config(tmp_path)
    with closing(build(tmp_path, roots=cfg.roots)) as graph:
        index = anchors.collect(graph)
        static = owners.static_findings(cfg, graph, index, 'HEAD', everything=True)
        checked = owners.check_findings(cfg, graph, index, 'HEAD', everything=True, static=static)
    for section in (static.section, checked.section):
        assert section[0].startswith('1 structure issues ') and [line for line in section if line[:1].isdigit()] == [
            section[0], next(line for line in section if line.startswith('1. row creation'))], section


def test_a_typed_member_given_a_constant_this_change_alters_is_new_in_the_unchanged_function(tmp_path):
    # D2: the declared set is the current one; the baseline code gave the member the constant's old value.
    use = ("import { K } from './consts';\nimport type { Row } from './types';\n"
           "export function make(): Row {\n  const row: Row = { kind: K.A };\n  return row;\n}\n")
    _commit(tmp_path, {'app/types.ts': "export type Kind = 'a' | 'b';\nexport interface Row { kind: Kind }\n",
                       'app/consts.ts': "export const K = { A: 'a' } as const;\n", 'app/use.ts': use})
    _write(tmp_path, {'app/consts.ts': "export const K = { A: 'z' } as const;\n"})
    found = _found(tmp_path)
    issue = _issue(found, 'values:Row.kind')
    assert issue.fresh == frozenset({_module(tmp_path, 'app/use.ts') + ':make'})
    assert issue.parts[0][1:3] == ('app/use.ts:make', "writes 'z' outside 'a'|'b'")
    assert _kinds(_deliver(found), issue.name) == [('red', 'make')]


def test_an_unrelated_declaration_added_beside_an_old_difference_leaves_it_old(tmp_path):
    # Whether a declarations finding is new is decided by that name's declarations alone, not the declaring file's.
    _commit(tmp_path, {'app/a.ts': "export type Kind = 'a' | 'b';\n", 'app/b.ts': "export type Kind = 'a' | 'b' | 'c';\n"})
    _write(tmp_path, {'app/b.ts': "export type Kind = 'a' | 'b' | 'c';\nexport type Other = 'p' | 'q';\n"})
    found = _found(tmp_path)
    kind = _issue(found, 'declarations:Kind')
    assert kind.fresh == frozenset()
    assert [line.kind for line in _deliver(found) if line.name == kind.name] == ['before']
    # The name's own declaration changing is new.
    _write(tmp_path, {'app/b.ts': "export type Kind = 'a' | 'b' | 'd';\nexport type Other = 'p' | 'q';\n"})
    assert _issue(_found(tmp_path), 'declarations:Kind').fresh == frozenset({''})


def test_a_declaration_whose_alias_now_names_other_values_is_new_though_its_file_is_unchanged(tmp_path):
    _commit(tmp_path, {'app/consts.ts': "export const KS = ['a', 'b'] as const;\n", 'app/b.ts': "export type Kind = 'a' | 'b';\n",
                       'app/a.ts': "import { KS } from './consts';\nexport type Kind = (typeof KS)[number];\n"})
    _write(tmp_path, {'app/consts.ts': "export const KS = ['a', 'c'] as const;\n"})
    found = _found(tmp_path)
    kind = _issue(found, 'declarations:Kind')
    assert kind.files == frozenset({'app/a.ts', 'app/b.ts'}) and kind.fresh == frozenset({''})
    assert [line.kind for line in _deliver(found) if line.name == kind.name] == ['impact']


def test_an_unrelated_model_added_to_a_schema_leaves_an_old_field_declaration_difference_old(tmp_path):
    enum = 'enum State {\n  open\n  shut\n}\n\nmodel Item {\n  id    String @id\n  state State\n}\n'
    _commit(tmp_path, {'prisma/schema.prisma': enum, 'app/state.ts': "export type State = 'open' | 'gone';\n"})
    _write(tmp_path, {'prisma/schema.prisma': enum + '\nmodel Other {\n  id String @id\n}\n'})
    found = _found(tmp_path)
    field = _issue(found, 'declarations:Item.state')
    assert field.fresh == frozenset() and field.files == frozenset({'prisma/schema.prisma', 'app/state.ts'})
    assert [line.kind for line in _deliver(found) if line.name == field.name] == ['before']
    # A member added to the enum is new.
    _write(tmp_path, {'prisma/schema.prisma': enum.replace('  shut\n', '  shut\n  held\n')})
    assert _issue(_found(tmp_path), 'declarations:Item.state').fresh == frozenset({''})


def test_a_python_declaration_is_new_only_when_its_own_members_change(tmp_path):
    other = 'from typing import Literal\n\nKind = Literal["a", "c"]\n\n\nclass Order:\n    def total(self):\n        return %d\n'
    _commit(tmp_path, {'app/__init__.py': '', 'app/a.py': 'from typing import Literal\n\nKind = Literal["a", "b"]\n',
                       'app/b.py': other % 1})
    _write(tmp_path, {'app/b.py': other % 2})
    assert _issue(_found(tmp_path), 'declarations:Kind').fresh == frozenset()
    _write(tmp_path, {'app/b.py': (other % 2).replace('"c"', '"d"')})
    assert _issue(_found(tmp_path), 'declarations:Kind').fresh == frozenset({''})


def test_a_python_enum_declaration_is_new_only_when_its_own_members_change(tmp_path):
    enum = 'from enum import Enum\n\n\nclass Status(Enum):\n    OPEN = "open"\n    %s = "%s"\n'
    other = enum % ('GONE', 'gone') + '\n\nclass Order:\n    def total(self):\n        return %d\n'
    _commit(tmp_path, {'app/__init__.py': '', 'app/a.py': enum % ('SHUT', 'shut'), 'app/b.py': other % 1})
    _write(tmp_path, {'app/b.py': other % 2})
    status = _issue(_found(tmp_path), 'declarations:Status')
    assert status.files == frozenset({'app/a.py', 'app/b.py'}) and status.fresh == frozenset()
    _write(tmp_path, {'app/b.py': (other % 2).replace('"gone"', '"lost"')})
    assert _issue(_found(tmp_path), 'declarations:Status').fresh == frozenset({''})


def test_known_fixed_is_said_only_for_a_family_every_check_of_which_judged_the_whole_project(tmp_path):
    from flowguard.intent.sources import Known
    _commit(tmp_path, {'limits.py': LIMITS % 3, 'pyproject.toml': '[tool.pytest.ini_options]\npythonpath=["."]\n',
                       'caps.py': 'def cap(days: int) -> bool:\n    return days <= 5\n'})      # a look-alike of chart
    _write(tmp_path, {'limits.py': LIMITS % 3 + '\n\ndef other():\n    return 1\n'})
    discovered = Known(id='limit-copies', sites=('limits.py:chart',), why='the owner deferred it', act='leave',
                       finding='copies:LIMIT')
    changed = Known(id='limit-alone', sites=('limits.py:chart',), why='the owner deferred it', act='leave',
                    finding='changed-alone:LIMIT')
    # pytest and check --static: copy discovery, which names copies of a reference, did not run; the changed-alone
    # comparison judges only what a change edits, so a finding of it gone is never fixed.
    found = _found(tmp_path)
    assert 'copies' not in found.ran and 'changed-alone' not in found.ran
    assert not [line for line in _deliver(found, known=(discovered, changed)) if line.kind == 'known fixed?']
    # check judges the copies of every reference only with --all (otherwise those this change touches: not caps.py).
    assert 'copies' not in _found(tmp_path, replay=True).ran
    assert 'copies' in _found(tmp_path, replay=True, everything=True).ran
    assert 'copies' not in _found(tmp_path).ran
    # Without a reference no copy discovery can name a copies finding: the structural check alone judges them all.
    _commit(tmp_path, {'limits.py': 'def chart(days):\n    return days <= 3\n'})
    _write(tmp_path, {'limits.py': 'def chart(days):\n    return days <= 4\n'})
    found = _found(tmp_path)
    gone = Known(id='fmt-copies', sites=('limits.py:chart',), why='the owner deferred it', act='leave', finding='copies:fmt')
    assert 'copies' in found.ran
    assert [(line.kind, line.name) for line in _deliver(found, known=(gone,))] == [('known fixed?', 'known.fmt-copies')]


def test_a_red_step_of_two_copies_changed_alone_is_ascii(tmp_path):
    text = LIMITS + '''

# flowguard: sensor LIMIT
def summary(days: int) -> bool:
    return days <= %d
'''
    _commit(tmp_path, {'limits.py': text % (3, 3), 'pyproject.toml': '[tool.pytest.ini_options]\npythonpath=["."]\n'})
    _write(tmp_path, {'limits.py': text % (4, 4)})
    cfg = load_config(tmp_path)
    with closing(build(tmp_path, roots=cfg.roots)) as graph:
        found = owners.changed_alone(cfg, graph, anchors.collect(graph), owners.Change(cfg, graph, 'HEAD'))
    issue = _issue(found, 'changed-alone:LIMIT')
    assert [part[3] for part in issue.parts] == ['make report, summary match reference chart(limits.py:2)'] * 2
    assert any('report\u3001summary' in line for line in found.red)     # the legacy red line keeps its text
    lines, _ = signals.deliver(found.issues, touched_functions=(), touched_files=(), extra=found.lines)
    assert all(ord(character) < 128 for line in lines for character in line.text + line.step)


def test_the_static_assembly_reads_the_deprecated_structure_section_once(tmp_path, capsys):
    entry = _write_state('setOne', field='note')
    _commit(tmp_path, {'prisma/schema.prisma': SCHEMA + GHOST, 'app/one.ts': entry,
                       'docs/owner.md': 'Ghost rows come from the nightly import.\n', '.flowguard/ledger.toml': DECISION})
    _write(tmp_path, {'app/one.ts': entry.replace("note: 'x'", "note: 'x', state: 'y'")})
    found = _found(tmp_path)
    assert [line.kind for line in found.lines] == ['impact']            # field_impact asked for the open writers
    assert len([line for line in capsys.readouterr().err.splitlines() if line.startswith('deprecated: ledger [structure]')]) == 1


def test_the_baseline_writes_are_read_once_for_every_writers_agreement_and_the_old_copies_only_when_files_changed(
        tmp_path, monkeypatch):
    from flowguard.intent import health
    agreements = ''.join(f'// flowguard: writers Item.{field} setState\n' for field in ('state', 'note'))
    _commit(tmp_path, {'prisma/schema.prisma': SCHEMA, 'app/owner.ts': _write_state('setState', comment=agreements),
                       'app/legacy.ts': _write_state('legacy') + _write_state('legacyNote', field='note'),
                       'app/x.ts': 'export function fmt(a: number) { if (a > 1) { return a + 1; } return a - 1; }\n',
                       'app/y.ts': 'export function fmt(a: number) { if (a > 2) { return a + 1; } return a - 2; }\n'})
    targets, before = [], []
    original, functions = owners.Change.baseline_writes, health._module_functions
    monkeypatch.setattr(owners.Change, 'baseline_writes',
                        lambda self, target=None, **options: targets.append(target) or original(self, target, **options))
    monkeypatch.setattr(health, '_module_functions', lambda change, **options: before.append(options.get('before', False))
                        or functions(change, **options))
    assert 'copies:fmt' in {issue.name for issue in _found(tmp_path).issues}
    assert True not in before              # nothing changed: the baseline code is the code
    _write(tmp_path, {'app/legacy.ts': _write_state('legacy', 'y') + _write_state('legacyNote', 'z', field='note')})
    found = _found(tmp_path)
    assert {issue.name for issue in found.issues} >= {'writer:Item.state', 'writer:Item.note'}
    assert set(targets) == {None} and True in before
