"""The `together` (pair) holes of round 22's E1 on the Planning Tool, each as one small fixture.

A pair finding is red when this change adds its member: (Issue.name, function) holds now and did not hold in the
baseline result, which the current registration gives for the baseline code (the writes of every changed file at the
baseline, the current operation tree, unless a function on that tree now calls differently). Asserted on the finding
(`health.Issue` fields) and on the lines `signals.deliver` gives it, not on rendered text.

- i3: the change edits only a helper, which stops writing the partner; the unchanged caller's member is new.
- w2: a partner written in the same function to another record (another selector) does not hold the pair.
- w4: a partner written only under a condition the trigger write is not under does not hold it.
- sib / fixCall: a module-level route callback is its own operation; a sibling handler's write does not hold it,
  a helper the handler calls does.
- fixP / a new agreement: an old violation stays old (before), also under an agreement this change adds.
"""
from contextlib import closing

from flowguard.intent import anchors, owners, signals
from flowguard.intent.config import load_config
from flowguard.structure import build
from tests.intent_engine.test_static_check import _commit, _write

SCHEMA = '''
    model Central {
      id        String @id
      orgUnitId String
      sapNumber Int
    }

    model Local {
      id           String @id
      unitId       String
      sapReference Int
    }

    model Node {
      id       Int  @id
      parentId Int
      level    Int
      isLeaf   Boolean
    }

    model Project {
      id       String @id
      leaderId String
    }

    model Member {
      id        String @id
      projectId String
      role      String
    }
'''
CENTRAL = 'together Central.orgUnitId Local.unitId'
NODE = 'together Node.parentId Node.level'
LEADER = 'together Project.leaderId Member.*'


def _agreements(*lines):
    return {'src/agreements.ts': ''.join(f'// flowguard: {line}\n' for line in lines) + 'export {};\n'}


def _pairs(root, base='HEAD'):
    """(the pair findings, the lines deliver gives them) for the working tree against `base`."""
    with closing(build(root)) as graph:
        change = owners.Change(load_config(root), graph, base)
        found = owners.owner_pairs(change, anchors.collect(graph))
        touched = change.touched()
        files = set(change.files)
    issues = [issue for issue in found.issues if issue.family == 'pair']
    lines, _ = signals.deliver(issues, touched_functions=touched, touched_files=files)
    return issues, lines, found


def _members(issues):
    return {(issue.name, function) for issue in issues for function, *_ in issue.parts}


def _fresh(issues):
    return {(issue.name, function) for issue in issues for function in issue.fresh}


def _red(lines):
    return {(line.name, line.function) for line in lines if line.kind == 'red'}


def _project(root, files, *agreements):
    return _commit(root, {'prisma/schema.prisma': SCHEMA, **_agreements(*agreements), **files})


# ---- the finding's fields -------------------------------------------------------------------------------

def test_a_pair_finding_names_its_family_subject_and_one_part_per_function(tmp_path):
    _project(tmp_path, {'src/central.ts': '''
        export const centralService = {
          async move(prisma: any, id: string, unit: string) {
            await prisma.central.update({ where: { id }, data: { orgUnitId: unit } });
          },
        };
    '''}, CENTRAL)
    _write(tmp_path, {'src/admin.ts': '''
        export async function editCentral(prisma: any, id: string, unit: string) {
          await prisma.central.update({ where: { id }, data: { orgUnitId: unit } });
          await prisma.central.update({ where: { id }, data: { orgUnitId: unit } });
        }
    '''})
    issues, lines, _ = _pairs(tmp_path)
    [issue] = issues
    name = 'pair:Central.orgUnitId>Local.unitId'
    assert (issue.name, issue.family, issue.subject) == (name, 'pair', 'together Central.orgUnitId')
    old, new = 'typescript/src/central.ts:move', 'typescript/src/admin.ts:editCentral'
    assert [part[0] for part in issue.parts] == [new, old]                  # one part per function, two writes of one
    assert dict((part[0], part[1:]) for part in issue.parts)[new] == (
        'src/admin.ts:editCentral', 'writes Central.orgUnitId without Local.unitId', 'also write Local.unitId in editCentral')
    assert issue.fresh == {new}
    assert [(line.kind, line.function) for line in lines] == [('red', new)]
    assert lines[0].text == 'together Central.orgUnitId: src/admin.ts:editCentral writes Central.orgUnitId without Local.unitId'


def test_without_a_baseline_no_pair_member_is_fresh(tmp_path):
    _project(tmp_path, {'src/admin.ts': '''
        export async function editCentral(prisma: any, id: string, unit: string) {
          await prisma.central.update({ where: { id }, data: { orgUnitId: unit } });
        }
    '''}, CENTRAL)
    issues, lines, _ = _pairs(tmp_path, base=None)
    assert _members(issues) == {('pair:Central.orgUnitId>Local.unitId', 'typescript/src/admin.ts:editCentral')}
    assert not _fresh(issues) and not lines


# ---- i3: a helper file stops writing the partner --------------------------------------------------------

CALLER = '''
    import { syncLocal } from './sync';
    export const centralService = {
      async move(prisma: any, id: string, unit: string) {
        const employee = await prisma.central.update({ where: { id }, data: { orgUnitId: unit } });
        await syncLocal(prisma, employee.sapNumber, unit);
      },
    };
'''
SYNC_WRITES = '''
    export async function syncLocal(prisma: any, sapReference: number, unit: string) {
      await prisma.local.updateMany({ where: { sapReference }, data: { unitId: unit } });
    }
'''
SYNC_READS = '''
    export async function syncLocal(prisma: any, sapReference: number, unit: string) {
      const rows = await prisma.local.findMany({ where: { sapReference }, select: { unitId: true } });
      return rows.filter((row: any) => row.unitId !== unit).length;
    }
'''


def test_a_helper_that_stops_writing_the_partner_makes_its_unchanged_callers_member_red(tmp_path):
    _project(tmp_path, {'src/central.ts': CALLER, 'src/sync.ts': SYNC_WRITES}, CENTRAL)
    assert _pairs(tmp_path)[0] == []                      # the helper writes the partner
    _write(tmp_path, {'src/sync.ts': SYNC_READS})
    issues, lines, found = _pairs(tmp_path)
    member = ('pair:Central.orgUnitId>Local.unitId', 'typescript/src/central.ts:move')
    assert _members(issues) == _fresh(issues) == _red(lines) == {member}
    assert [line.kind for line in lines] == ['red']


def test_a_helper_that_never_wrote_the_partner_leaves_the_old_member_old(tmp_path):
    _project(tmp_path, {'src/central.ts': CALLER, 'src/sync.ts': SYNC_READS}, CENTRAL)
    _write(tmp_path, {'src/sync.ts': SYNC_READS.replace('.length', '.length + 0')})
    issues, lines, _ = _pairs(tmp_path)
    member = ('pair:Central.orgUnitId>Local.unitId', 'typescript/src/central.ts:move')
    assert _members(issues) == {member} and not _fresh(issues) and not lines


# ---- w2: the partner written to another record in the same function -------------------------------------

def _move(*statements, field=''):
    body = ''.join(f'    {statement}\n' for statement in statements)
    return ('export async function reparent(prisma: any, id: number, parent: number, level: number) {\n'
            f'  await prisma.node.update({{ where: {{ id }}, data: {{ parentId: parent{field} }} }});\n{body}}}\n')


def _reparent(tmp_path, source):
    _project(tmp_path, {'src/keep.ts': 'export const keep = 1;\n'}, NODE)
    _write(tmp_path, {'src/node.ts': source})
    issues, lines, _ = _pairs(tmp_path)
    return _red(lines)


REPARENT = {('pair:Node.parentId>Node.level', 'typescript/src/node.ts:reparent')}


def test_a_partner_written_to_another_record_of_the_same_model_does_not_hold_the_pair(tmp_path):
    # E1 D-w2 / C-w2: the new parent's level, not the moved node's.
    assert _reparent(tmp_path, _move('await prisma.node.update({ where: { id: parent }, data: { level } });')) == REPARENT


def test_a_partner_written_to_the_same_record_in_another_call_holds_the_pair(tmp_path):
    assert _reparent(tmp_path, _move('await prisma.node.update({ where: { id }, data: { level } });')) == set()


def test_a_partner_in_the_same_call_holds_the_pair(tmp_path):
    assert _reparent(tmp_path, _move(field=', level')) == set()


def test_a_partner_whose_record_is_not_readable_still_holds_the_pair(tmp_path):
    # D20: a selector held in a variable is not compared; the write counts.
    assert _reparent(tmp_path, _move('const where = { id: parent };',
                                     'await prisma.node.update({ where, data: { level } });')) == set()


def _home(tmp_path, where):
    _project(tmp_path, {'src/keep.ts': 'export const keep = 1;\n'}, CENTRAL)
    _write(tmp_path, {'src/home.ts': f'''
        export async function reassign(prisma: any, id: string, unit: string) {{
          const employee = await prisma.central.findUnique({{ where: {{ id }}, select: {{ sapNumber: true }} }});
          await prisma.central.update({{ where: {{ id }}, data: {{ orgUnitId: unit }} }});
          await prisma.local.updateMany({{ where: {{ {where} }}, data: {{ unitId: unit }} }});
        }}
    '''})
    return _red(_pairs(tmp_path)[1])


def test_a_partner_of_another_model_selected_by_the_same_text_does_not_hold_the_pair(tmp_path):
    # E1 A-w2: the Central id used as the local employee's id.
    assert _home(tmp_path, 'id') == {('pair:Central.orgUnitId>Local.unitId', 'typescript/src/home.ts:reassign')}


def test_a_partner_of_another_model_selected_by_its_own_key_holds_the_pair(tmp_path):
    # E1 A-fix stays green.
    assert _home(tmp_path, 'sapReference: employee.sapNumber') == set()


def test_a_partner_in_another_function_holds_the_pair_whatever_its_selector(tmp_path):
    # Only writes of one function are compared by record (D20); a helper's write counts as before (E1 i1).
    _project(tmp_path, {'src/keep.ts': 'export const keep = 1;\n'}, NODE)
    _write(tmp_path, {'src/node.ts': '''
        async function storeLevel(prisma: any, parent: number, level: number) {
          await prisma.node.update({ where: { id: parent }, data: { level } });
        }
        export async function reparent(prisma: any, id: number, parent: number, level: number) {
          await prisma.node.update({ where: { id }, data: { parentId: parent } });
          await storeLevel(prisma, parent, level);
        }
    '''})
    assert _red(_pairs(tmp_path)[1]) == set()


# ---- w4: the partner written only under a condition ------------------------------------------------------

def test_a_partner_in_a_conditional_spread_does_not_hold_the_pair(tmp_path):
    # E1 D-w4.
    assert _reparent(tmp_path, _move(field=', ...(level < 0 && { level: 0 })')) == REPARENT


def test_a_partner_in_one_branch_of_a_conditional_object_does_not_hold_the_pair(tmp_path):
    assert _reparent(tmp_path, _move(field=', ...(level < 0 ? { level: 0 } : {})')) == REPARENT


def test_a_partner_in_both_branches_or_under_the_triggers_own_condition_holds_the_pair(tmp_path):
    assert _reparent(tmp_path, _move(field=', ...(level < 0 ? { level: 0 } : { level })')) == set()
    _write(tmp_path, {'src/node.ts': '''
        export async function reparent(prisma: any, id: number, parent: number, level: number) {
          await prisma.node.update({ where: { id }, data: { ...(parent > 0 && { parentId: parent, level }) } });
        }
    '''})
    assert _red(_pairs(tmp_path)[1]) == set()


def test_a_partner_under_another_condition_of_a_conditional_trigger_counts_not_confirmed(tmp_path):
    # The Planning Tool's org-unit update: both fields in their own spread, their conditions tied by a variable.
    _project(tmp_path, {'src/keep.ts': 'export const keep = 1;\n'}, NODE)
    _write(tmp_path, {'src/node.ts': '''
        export async function patch(prisma: any, id: number, input: any) {
          const level = input.parent !== undefined ? 1 : undefined;
          await prisma.node.update({ where: { id }, data: {
            ...(level !== undefined && { level }),
            ...(input.parent !== undefined && { parentId: input.parent }),
          } });
        }
        export async function other(prisma: any, id: number, parent: number) {
          await prisma.node.update({ where: { id }, data: { parentId: parent } });
        }
    '''})
    issues, lines, _ = _pairs(tmp_path)
    [issue] = issues
    assert [function for function, *_ in issue.parts] == ['typescript/src/node.ts:other']
    assert issue.detail[:1] == ('src/node.ts:patch: src/node.ts:patch writes Node.level, but it is written under another '
                                'condition: not confirmed',), issue.detail


def test_conditional_partner_fields_are_marked_in_the_write_facts(tmp_path):
    _project(tmp_path, {'src/node.ts': _move(field=', ...(level < 0 && { level: 0 }), isLeaf: true')}, NODE)
    with closing(build(tmp_path)) as graph:
        rows = {row['field']: row for row in graph.writes('Node')}
    assert rows['level'].get('conditional') and not rows['parentId'].get('conditional') and not rows['isLeaf'].get('conditional')
    assert rows['parentId']['selector'] == rows['level']['selector'] == [['id', 'id']]


# ---- module-level route callbacks: each handler is its own operation ------------------------------------

ROUTES = '''
    import { memberService } from './members';
    const router: any = {};
    router.put('/:id/leader', async (req: any, res: any) => {
      const project = await prisma.project.update({ where: { id: req.params.id }, data: { leaderId: req.body.id } });
    %s  res.json(project);
    });
    %s
    export { router };
'''
MEMBERS = '''
    export const memberService = {
      async addLeader(prisma: any, projectId: string, id: string) {
        await prisma.member.create({ data: { projectId, id, role: 'LEAD' } });
      },
    };
'''
SIBLING = '''
    router.post('/:id/observer', async (req: any, res: any) => {
      res.json(await prisma.member.create({ data: { projectId: req.params.id, id: req.body.id, role: 'MEMBER' } }));
    });
'''


def _route(tmp_path, inside, after=''):
    """The change adds the leader handler (E1 B-r3) with `inside` in its body and `after` it."""
    _project(tmp_path, {'src/members.ts': MEMBERS, 'src/routes.ts': 'const router: any = {};\nexport { router };\n'}, LEADER)
    _write(tmp_path, {'src/routes.ts': ROUTES % (inside, after)})
    issues, lines, found = _pairs(tmp_path)
    return issues, lines, found


def test_a_sibling_handler_that_writes_the_partner_does_not_hold_the_pair(tmp_path):
    # E1 B-r3sib: both handlers used to be one `<module>` operation.
    issues, lines, found = _route(tmp_path, '', SIBLING)
    [member] = _red(lines)
    assert member[0] == 'pair:Project.leaderId>Member.*' and member[1].startswith('typescript/src/routes.ts:<anonymous@')
    assert any('missing paired write' in line for line in found.red), found.red


def test_a_handler_that_calls_the_helper_writing_the_partner_holds_the_pair(tmp_path):
    # E1 B-r3fixCall: the handler's own calls are its operation (4.2.1 read the module's calls only).
    issues, lines, found = _route(tmp_path, '  await memberService.addLeader(prisma, project.id, req.body.id);\n')
    assert _red(lines) == set() and not found.red, (found.red, lines)


def test_a_handler_that_writes_the_partner_itself_holds_the_pair(tmp_path):
    # E1 B-r3fixDirect.
    issues, lines, found = _route(tmp_path, "  await prisma.member.create({ data: { projectId: project.id, id: req.body.id, role: 'LEAD' } });\n")
    assert _red(lines) == set() and not found.red


def test_a_service_write_is_held_by_the_handler_that_calls_it_and_writes_the_partner(tmp_path):
    # The handler is a caller of the operation: its own writes, which 4.2.1 counted as the module's, still count.
    _project(tmp_path, {'src/service.ts': '''
        export const projectService = {
          async setLeader(prisma: any, id: string, leader: string) {
            await prisma.project.update({ where: { id }, data: { leaderId: leader } });
          },
        };
    ''', 'src/routes.ts': '''
        import { projectService } from './service';
        const router: any = {};
        router.put('/:id/leader', async (req: any, res: any) => {
          await projectService.setLeader(prisma, req.params.id, req.body.id);
          res.json(await prisma.member.create({ data: { projectId: req.params.id, id: req.body.id, role: 'LEAD' } }));
        });
        router.post('/:id/other', async (req: any, res: any) => {
          res.json(await prisma.project.update({ where: { id: req.params.id }, data: { leaderId: req.body.id } }));
        });
        export { router };
    '''}, LEADER)
    issues, lines, found = _pairs(tmp_path, base=None)
    assert [function for issue in issues for function, *_ in issue.parts] == ['typescript/src/routes.ts:<anonymous@7,27>']


def test_an_old_handler_stays_old_when_lines_above_it_move(tmp_path):
    # A callback is named by where it starts; its member keeps its identity by the call that registers it.
    _project(tmp_path, {'src/members.ts': MEMBERS, 'src/routes.ts': ROUTES % ('', '')}, LEADER)
    _write(tmp_path, {'src/routes.ts': '// a new first line\n' + (ROUTES % ('', SIBLING)).lstrip('\n')})
    issues, lines, _ = _pairs(tmp_path)
    assert len(_members(issues)) == 1 and not _fresh(issues) and not _red(lines)


# ---- fixP and a new agreement: what was broken at the baseline stays old ---------------------------------

OLD_VIOLATION = '''
    export const nodeService = {
      async move(prisma: any, id: number, parent: number) {
        await prisma.node.update({ where: { id }, data: { parentId: parent } });
      },
    %s};
'''
FIXED_METHOD = '''
      async reparent(prisma: any, id: number, parent: number, level: number) {
        await prisma.node.update({ where: { id }, data: { parentId: parent, level } });
      },
'''
MOVE = ('pair:Node.parentId>Node.level', 'typescript/src/node.ts:move')


def test_a_fixed_method_beside_an_old_violation_adds_no_red_and_the_old_member_is_before_when_touched(tmp_path):
    # E1 B-fixP / D-fixP.
    _project(tmp_path, {'src/node.ts': OLD_VIOLATION % ''}, NODE)
    _write(tmp_path, {'src/node.ts': OLD_VIOLATION % FIXED_METHOD})
    issues, lines, _ = _pairs(tmp_path)
    assert _members(issues) == {MOVE} and not _fresh(issues) and not lines
    [issue] = issues
    before, _ = signals.deliver(issues, touched_functions={MOVE[1]}, touched_files=())
    assert [(line.kind, line.name, line.function) for line in before] == [('before', *MOVE)]


def test_an_agreement_this_change_adds_over_an_old_violation_gives_before_not_red(tmp_path):
    # D2: the current registration applied to the baseline code; the old violation was already there.
    _commit(tmp_path, {'prisma/schema.prisma': SCHEMA, 'src/node.ts': OLD_VIOLATION % ''})
    _write(tmp_path, _agreements(NODE))
    issues, lines, found = _pairs(tmp_path)
    assert _members(issues) == {MOVE} and not _fresh(issues) and not _red(lines)


# ---- the callee-stability guard: the baseline is inexact when the tree calls differently now ---------------

def test_a_caller_that_stops_calling_the_partners_writer_makes_its_member_red(tmp_path):
    source = '''
        async function storeLevel(prisma: any, id: number, level: number) {
          await prisma.node.update({ where: { id }, data: { level } });
        }
        export async function reparent(prisma: any, id: number, parent: number, level: number) {
          await prisma.node.update({ where: { id }, data: { parentId: parent } });
          %s
        }
    '''
    _project(tmp_path, {'src/node.ts': source % 'await storeLevel(prisma, id, level);'}, NODE)
    _write(tmp_path, {'src/node.ts': source % 'return level;'})
    issues, lines, _ = _pairs(tmp_path)
    assert _red(lines) == {('pair:Node.parentId>Node.level', 'typescript/src/node.ts:reparent')}


def test_a_function_that_stops_calling_the_trigger_makes_the_triggers_member_red(tmp_path):
    # At the baseline `apply` called `setParent` and wrote the partner itself: one operation. Now nobody calls it.
    _project(tmp_path, {'src/node.ts': '''
        export async function setParent(prisma: any, id: number, parent: number) {
          await prisma.node.update({ where: { id }, data: { parentId: parent } });
        }
    ''', 'src/apply.ts': '''
        import { setParent } from './node';
        export async function apply(prisma: any, id: number, parent: number) {
          await setParent(prisma, id, parent);
          await prisma.node.update({ where: { id }, data: { level: 1 } });
        }
    '''}, NODE)
    assert _pairs(tmp_path)[0] == []
    _write(tmp_path, {'src/apply.ts': '''
        export async function apply(prisma: any, id: number, parent: number) {
          await prisma.node.update({ where: { id }, data: { level: 1 } });
        }
    '''})
    issues, lines, _ = _pairs(tmp_path)
    assert _red(lines) == {('pair:Node.parentId>Node.level', 'typescript/src/node.ts:setParent')}


def test_a_new_caller_of_an_old_violation_leaves_it_old(tmp_path):
    # A call this change adds can only bring partners into the tree: the baseline read with the current tree holds.
    _project(tmp_path, {'src/node.ts': OLD_VIOLATION % ''}, NODE)
    _write(tmp_path, {'src/relocate.ts': '''
        import { nodeService } from './node';
        export async function relocate(prisma: any, id: number, parent: number) {
          await nodeService.move(prisma, id, parent);
          return parent;
        }
    '''})
    issues, lines, _ = _pairs(tmp_path)
    assert _members(issues) == {MOVE} and not _fresh(issues) and not lines


def test_a_member_whose_partner_was_written_by_a_function_this_change_removes_is_red(tmp_path):
    # `reparent` still spells the call, but `storeLevel` is gone, so the current tree no longer reaches its write.
    _project(tmp_path, {'src/lib.ts': '''
        export async function storeLevel(prisma: any, id: number, level: number) {
          await prisma.node.update({ where: { id }, data: { level } });
        }
    ''', 'src/node.ts': '''
        import { storeLevel } from './lib';
        export async function reparent(prisma: any, id: number, parent: number, level: number) {
          await prisma.node.update({ where: { id }, data: { parentId: parent } });
          await storeLevel(prisma, id, level);
        }
    '''}, NODE)
    assert _pairs(tmp_path)[0] == []
    (tmp_path / 'src/lib.ts').unlink()
    issues, lines, _ = _pairs(tmp_path)
    [issue] = issues
    assert _red(lines) == {('pair:Node.parentId>Node.level', 'typescript/src/node.ts:reparent')}
    assert [text for text in issue.detail if 'this change removes' in text] == [
        'src/node.ts:reparent counts as new: typescript/src/node.ts:reparent calls typescript/src/lib.ts:storeLevel, '
        'which this change removes, so its baseline cannot be read'], issue.detail


# ---- the guard reads what the tree lost, not every call a changed file dropped ----------------------------

def test_an_unrelated_file_that_drops_a_call_of_a_tree_functions_name_leaves_the_old_member_old(tmp_path):
    # `report` drops `validator.check`: `check` names a function lower in `move`'s tree, which cannot shrink it.
    _project(tmp_path, {'src/util.ts': '''
        export function check(id: number) { return id > 0; }
    ''', 'src/node.ts': '''
        import { check } from './util';
        export async function move(prisma: any, id: number, parent: number) {
          check(id);
          await prisma.node.update({ where: { id }, data: { parentId: parent } });
        }
    ''', 'src/report.ts': '''
        const validator: any = {};
        export function report(x: number) { validator.check(x); return x; }
    '''}, NODE)
    _write(tmp_path, {'src/report.ts': '''
        export function report(x: number) { return x; }
    '''})
    issues, lines, _ = _pairs(tmp_path)
    assert _members(issues) == {('pair:Node.parentId>Node.level', 'typescript/src/node.ts:move')}
    assert not _fresh(issues), [issue.detail for issue in issues]


def test_a_test_or_another_holders_call_that_a_change_drops_leaves_the_old_member_old(tmp_path):
    # A test is not part of the operation, and `otherService.move` is another function than `nodeService.move`.
    _project(tmp_path, {'src/node.ts': OLD_VIOLATION % '', 'src/other.ts': '''
        export const otherService = {
          move(id: number) { return id; },
        };
        export function relocate(id: number) { return otherService.move(id); }
    ''', 'tests/node.test.ts': '''
        import { nodeService } from '../src/node';
        export async function moveIt(prisma: any) { await nodeService.move(prisma, 1, 2); }
    '''}, NODE)
    _write(tmp_path, {'src/other.ts': '''
        export const otherService = {
          move(id: number) { return id; },
        };
        export function relocate(id: number) { return id; }
    ''', 'tests/node.test.ts': '''
        export async function moveIt(prisma: any) { return prisma; }
    '''})
    issues, lines, _ = _pairs(tmp_path)
    assert _members(issues) == {MOVE} and not _fresh(issues), [issue.detail for issue in issues]


LIB = '''
    export async function sync(prisma: any, id: number, level: number) {
      await prisma.node.update({ where: { id }, data: { level } });
    }
'''
LIB_SILENT = '''
    export async function sync(prisma: any, id: number, level: number) {
      return level;
    }
'''
CALLS_SYNC = '''
    import { sync } from './%s';
    export async function reparent(prisma: any, id: number, parent: number, level: number) {
      await prisma.node.update({ where: { id }, data: { parentId: parent } });
      await sync(prisma, id, level);
    }
'''


def test_a_caller_that_imports_the_same_name_from_another_file_makes_its_member_red(tmp_path):
    # The call reads `sync` as before, but from a file whose `sync` does not write the partner.
    _project(tmp_path, {'src/lib.ts': LIB, 'src/lib2.ts': LIB_SILENT, 'src/node.ts': CALLS_SYNC % 'lib'}, NODE)
    assert _pairs(tmp_path)[0] == []
    _write(tmp_path, {'src/node.ts': CALLS_SYNC % 'lib2'})
    issues, lines, _ = _pairs(tmp_path)
    assert _members(issues) == _fresh(issues) == _red(lines) == REPARENT, [issue.detail for issue in issues]


def test_a_python_caller_that_imports_the_same_name_from_another_module_makes_its_member_red(tmp_path):
    store = '''
        # flowguard: owner hires.reserved with=hires.state=held
        from shop.%s import hold


        def reserve(db, hire_id):
            db.execute("UPDATE hires SET reserved = 1 WHERE id = ?", (hire_id,))
            hold(db, hire_id)
    '''
    _commit(tmp_path, {'shop/__init__.py': '', 'shop/store.py': store % 'lib', 'shop/lib.py': '''
        def hold(db, hire_id):
            db.execute("UPDATE hires SET state = 'held' WHERE id = ?", (hire_id,))
    ''', 'shop/lib2.py': '''
        def hold(db, hire_id):
            return hire_id
    '''})
    assert _pairs(tmp_path)[0] == []
    _write(tmp_path, {'shop/store.py': store % 'lib2'})
    issues, lines, _ = _pairs(tmp_path)
    member = {('pair:hires.reserved>hires.state=held', 'shop.store:reserve')}
    assert _members(issues) == _fresh(issues) == _red(lines) == member, [issue.detail for issue in issues]


MID = '''
    import { storeLevel } from './store';
    export async function sync(prisma: any, id: number, level: number) {
      await storeLevel(prisma, id, level);
    }
'''
STORE = '''
    export async function storeLevel(prisma: any, id: number, level: number) {
      await prisma.node.update({ where: { id }, data: { level } });
    }
'''


def test_a_helper_moved_to_a_new_file_without_the_call_that_wrote_the_partner_makes_the_caller_red(tmp_path):
    # mid.ts:sync called the partner's writer; the change deletes it and imports a new sync that does not.
    _project(tmp_path, {'src/store.ts': STORE, 'src/mid.ts': MID, 'src/node.ts': CALLS_SYNC % 'mid'}, NODE)
    assert _pairs(tmp_path)[0] == []
    (tmp_path / 'src/mid.ts').unlink()
    _write(tmp_path, {'src/mid2.ts': LIB_SILENT, 'src/node.ts': CALLS_SYNC % 'mid2'})
    issues, lines, _ = _pairs(tmp_path)
    assert _members(issues) == _fresh(issues) == _red(lines) == REPARENT, [issue.detail for issue in issues]


def test_a_helper_called_by_name_that_this_change_replaces_makes_the_unchanged_caller_red(tmp_path):
    # `reparent` calls `sync` by name alone (no import) and stays as it is; the change deletes the `sync` that
    # called the partner's writer and adds one that does not.
    caller = CALLS_SYNC.replace("    import { sync } from './%s';\n", '')
    _project(tmp_path, {'src/store.ts': STORE, 'src/mid.ts': MID, 'src/node.ts': caller}, NODE)
    assert _pairs(tmp_path)[0] == []
    (tmp_path / 'src/mid.ts').unlink()
    _write(tmp_path, {'src/mid2.ts': LIB_SILENT})
    issues, lines, _ = _pairs(tmp_path)
    assert _members(issues) == _fresh(issues) == _red(lines) == REPARENT, [issue.detail for issue in issues]


def test_module_code_that_stops_calling_the_member_makes_it_red(tmp_path):
    # At the baseline the seed script's own code called setParent and wrote the partner: one operation.
    _project(tmp_path, {'src/node.ts': '''
        export async function setParent(prisma: any, id: number, parent: number) {
          await prisma.node.update({ where: { id }, data: { parentId: parent } });
        }
    ''', 'src/seed.ts': '''
        import { setParent } from './node';
        const prisma: any = {};
        await setParent(prisma, 1, 2);
        await prisma.node.update({ where: { id: 1 }, data: { level: 1 } });
    '''}, NODE)
    assert _pairs(tmp_path)[0] == []
    _write(tmp_path, {'src/seed.ts': '''
        const prisma: any = {};
        await prisma.node.update({ where: { id: 1 }, data: { level: 1 } });
    '''})
    issues, lines, _ = _pairs(tmp_path)
    assert _red(lines) == {('pair:Node.parentId>Node.level', 'typescript/src/node.ts:setParent')}, [i.detail for i in issues]


# ---- callbacks keep their identity by how they are registered and by their code ----------------------------

LEADER_ROUTES = '''
    %s
    import { projectService } from './service';
    const router: any = {};
    router.put('/:id/leader', async (req: any, res: any) => {
      await projectService.setLeader(prisma, req.params.id, req.body.id);
      res.json(await prisma.member.create({ data: { projectId: req.params.id, id: req.body.id, role: '%s' } }));
    });
    export { router };
'''
SET_LEADER = '''
    export const projectService = {
      async setLeader(prisma: any, id: string, leader: string) {
        await prisma.project.update({ where: { id }, data: { leaderId: leader } });
      },
    };
'''
SET_LEADER_MEMBER = ('pair:Project.leaderId>Member.role=LEAD', 'typescript/src/service.ts:setLeader')


def test_a_handler_that_stops_writing_the_partner_value_while_lines_above_it_move_makes_the_member_red(tmp_path):
    _project(tmp_path, {'src/service.ts': SET_LEADER, 'src/routes.ts': LEADER_ROUTES % ('', 'LEAD')},
             'together Project.leaderId Member.role=LEAD')
    assert _pairs(tmp_path)[0] == []
    _write(tmp_path, {'src/routes.ts': LEADER_ROUTES % ('// moved\n// moved\n', 'MEMBER')})
    issues, lines, _ = _pairs(tmp_path)
    assert _members(issues) == _fresh(issues) == _red(lines) == {SET_LEADER_MEMBER}, [i.detail for i in issues]


USE = '''
    app.use(async (req: any, res: any) => {
      await prisma.project.update({ where: { id: req.params.id }, data: { leaderId: req.body.id } });
      %s
    });
'''


def test_a_new_handler_registered_like_an_old_one_is_new(tmp_path):
    # The new handler is inserted before the old one, which this change fixes: the new one is not the old one.
    _project(tmp_path, {'src/members.ts': MEMBERS, 'src/app.ts': 'const app: any = {};\n' + USE % ''}, LEADER)
    fix = "await prisma.member.create({ data: { projectId: req.params.id, id: req.body.id, role: 'LEAD' } });"
    _write(tmp_path, {'src/app.ts': 'const app: any = {};\n' + USE % 'res.json(1);' + USE % fix})
    issues, lines, _ = _pairs(tmp_path)
    [member] = _members(issues)
    assert _fresh(issues) == _red(lines) == {member}, [i.detail for i in issues]


def test_an_old_handler_this_change_edits_is_before(tmp_path):
    # The edited handler is touched (`Change.touched` names it as the pair does), so its old violation shows.
    _project(tmp_path, {'src/members.ts': MEMBERS, 'src/routes.ts': ROUTES % ('', '')}, LEADER)
    _write(tmp_path, {'src/routes.ts': ROUTES % ('  console.log(project.id);\n', '')})
    issues, lines, _ = _pairs(tmp_path)
    [member] = _members(issues)
    assert not _fresh(issues) and [(line.kind, line.name, line.function) for line in lines] == [('before', *member)]


# ---- w2 and w4: what the review of the first candidate found -----------------------------------------------

def test_a_create_of_the_triggers_own_model_in_its_function_does_not_hold_an_update(tmp_path):
    # A create makes another record than the one the trigger's `where` selects.
    assert _reparent(tmp_path, _move('await prisma.node.create({ data: { id: parent + 1, level } });')) == REPARENT


def _branches(data):
    return ('export async function reparent(prisma: any, id: number, parent: number, level: number, moving: boolean) {\n'
            f'  await prisma.node.update({{ where: {{ id }}, data: {data} }});\n}}\n')


def test_a_trigger_and_a_partner_in_two_branches_of_one_conditional_do_not_hold_the_pair(tmp_path):
    assert _reparent(tmp_path, _branches('moving ? { parentId: parent } : { level }')) == REPARENT
    for data in ('{ ...(moving ? { parentId: parent } : { level }) }', '{ parentId: parent } || { level }',
                 '{ ...(moving ? { parentId: parent } : null ?? { level }) }'):
        _write(tmp_path, {'src/node.ts': _branches(data)})
        assert _red(_pairs(tmp_path)[1]) == REPARENT, data


def test_the_branch_of_a_conditional_is_part_of_its_mark(tmp_path):
    _project(tmp_path, {'src/node.ts': _branches('moving ? { parentId: parent } : { level }')}, NODE)
    with closing(build(tmp_path)) as graph:
        rows = {row['field']: row['conditional'] for row in graph.writes('Node')}
    assert rows == {'parentId': ['2:51?'], 'level': ['2:51:']}


# ---- D20: a hold that is not confirmed --------------------------------------------------------------------

def test_a_hold_that_is_not_confirmed_is_noted_only_on_a_finding_of_its_agreement(tmp_path):
    # An unreadable `where` still holds the pair (D20). The note rides on the agreement's finding, as its detail; an
    # agreement with no member missing its partner has no finding to carry it.
    _project(tmp_path, {'src/keep.ts': 'export const keep = 1;\n'}, NODE)
    unread = _move('const where = { id: parent };', 'await prisma.node.update({ where, data: { level } });')
    _write(tmp_path, {'src/node.ts': unread})
    assert _pairs(tmp_path)[0] == []
    _write(tmp_path, {'src/node.ts': unread + OLD_VIOLATION % ''})
    [issue] = _pairs(tmp_path)[0]
    assert [function for function, *_ in issue.parts] == [MOVE[1]]
    assert issue.detail[:1] == ('src/node.ts:reparent: src/node.ts:reparent writes Node.level, but its where cannot be '
                                'read: not confirmed',), issue.detail


# ---- the baseline reads only what the map reads -------------------------------------------------------------

def test_a_deleted_file_the_map_never_reads_gives_the_baseline_nothing(tmp_path):
    # `.flowguard/**` and `[tool.flowguard] exclude` are never mapped, so they held no write at the baseline either.
    retired = '''
        def reserve(db, hire_id):
            db.execute("UPDATE hires SET reserved = 1 WHERE id = ?", (hire_id,))
    '''
    _commit(tmp_path, {'pyproject.toml': '[tool.flowguard]\nexclude = ["vendor/**"]\n', 'shop/__init__.py': '',
                       'shop/store.py': '# flowguard: owner hires.reserved with=hires.state=held\nKEEP = 1\n',
                       '.flowguard/models/retired.py': retired, 'vendor/tool.py': retired, 'shop/old.py': retired})
    for path in ('.flowguard/models/retired.py', 'vendor/tool.py', 'shop/old.py'):
        (tmp_path / path).unlink()
    with closing(build(tmp_path)) as graph:
        change = owners.Change(load_config(tmp_path), graph, 'HEAD')
        assert {path: change.module(path) for path in sorted(change.baseline_paths()) if path.endswith('.py')} == {
            '.flowguard/models/retired.py': None, 'shop/old.py': 'shop.old', 'vendor/tool.py': None}
        assert {row['file'] for row in change.baseline_writes('hires.reserved')} == {'shop/old.py'}
