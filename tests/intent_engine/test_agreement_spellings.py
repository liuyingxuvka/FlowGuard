"""New agreement spellings retain the existing facts and actual writer identities."""
from contextlib import closing
import ast
from pathlib import Path
import textwrap

import pytest

from flowguard.intent import anchors, owners
from flowguard.intent.config import load_config
from flowguard.structure import build

ACCOUNT_SCHEMA = 'model Account {\n  id Int @id\n  status String\n  changed Boolean\n}\n'


def _files(root, files):
    for name, source in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(textwrap.dedent(source).lstrip(), encoding='utf-8')


def _facts(source):
    source = textwrap.dedent(source).lstrip()
    return anchors.source_facts(ast.parse(source), source, 'policy', 'policy.py')


def test_python_same_and_reference_preserve_units_projection_and_fields():
    facts = _facts('''
        from typing import Annotated
        # flowguard: same LENGTH ref(x: m) -> result[0] fields limit=3
        def reference(x: Annotated[int, 'm']):
            return x < 3, x
        # flowguard: same LENGTH(x: m) -> result[0] fields limit=3
        def copy(x: Annotated[int, 'm']):
            return x < 3, x
    ''')
    assert not facts.get('anchor_issues')
    first, second = facts['anchors']
    assert [(row['kind'], row['name'], row['qual'], row['owner']) for row in (first, second)] == [
        ('sensor', 'LENGTH', 'reference', True), ('sensor', 'LENGTH', 'copy', False)]
    assert first['parameters'][0]['unit'] == 'm'
    assert first['projection'] == second['projection'] == 'result[0]'
    assert first['fields'] == second['fields'] == (('limit', '3'),)


@pytest.mark.parametrize('operation', ['create', 'update'])
def test_together_keeps_partner_values_and_operation(operation):
    facts = _facts(f'# flowguard: together Job.phase Job.state=READY,Job.owner on={operation}\n')
    assert not facts.get('anchor_issues')
    agreement, = facts['anchors']
    assert agreement['kind'] == 'owner'
    assert agreement['name'] == 'Job.phase'
    assert agreement['pairs'] == ('Job.state=READY', 'Job.owner')
    assert agreement['on'] == operation


def test_new_python_positions_follow_configured_import_roots(tmp_path):
    _files(tmp_path, {
        'pyproject.toml': '[tool.flowguard]\nroots=["src"]\n',
        'src/policy.py': '''
            # flowguard: writers account.status src/allowed.py:save
            # flowguard: together account.status account.changed except=src/allowed.py:save(owner approved)
        ''',
        'src/allowed.py': '''
            def save(db):
                db.execute("UPDATE account SET status = 'ready'")
        ''',
        'src/other.py': '''
            def save(db):
                db.execute("UPDATE account SET status = 'ready'")
        ''',
    })
    with closing(build(tmp_path, tmp_path / 'map.sqlite', workers=1)) as graph:
        index = anchors.collect(graph)
        agreement, = index.named('account.status')
        assert agreement.writers == ('allowed:save',)
        assert agreement.alone == ('allowed:save(owner approved)',)
        assert not [issue for issue in index.issues if issue.name == 'account.status']
        assert graph.node(agreement.writers[0])['file'] == 'src/allowed.py'
        found = owners.owner_writes(owners.Change(load_config(tmp_path), graph, None), index)
    issue, = found.issues
    assert [part[1] for part in issue.parts] == ['src/other.py:save']      # allowed.py's save is the writer


@pytest.mark.parametrize('suffix', ['py', 'ts'])
def test_a_new_bare_writer_does_not_authorize_the_same_name_in_another_file(tmp_path, suffix):
    if suffix == 'py':
        local = '''
            # flowguard: writers account.status save
            def save(db):
                db.execute("UPDATE account SET status = 'ready'")
        '''
        other = '''
            def save(db):
                db.execute("UPDATE account SET status = 'ready'")
        '''
        field = 'account.status'
    else:
        local = '''
            // flowguard: writers Account.status save
            export function save(prisma: any) {
              return prisma.account.update({ where: { id: 1 }, data: { status: 'ready' } });
            }
        '''
        other = '''
            export function save(prisma: any) {
              return prisma.account.update({ where: { id: 2 }, data: { status: 'ready' } });
            }
        '''
        field = 'Account.status'
    _files(tmp_path, {f'local.{suffix}': local, f'other.{suffix}': other,
                      **({'prisma/schema.prisma': ACCOUNT_SCHEMA} if suffix == 'ts' else {})})
    with closing(build(tmp_path, tmp_path / 'map.sqlite', workers=1)) as graph:
        index = anchors.collect(graph)
        agreement, = index.named(field)
        assert graph.node(agreement.writers[0])['file'] == f'local.{suffix}'
        assert {row['file'] for row in graph.writes(field, by_name=True)} == {f'local.{suffix}', f'other.{suffix}'}
        found = owners.owner_writes(owners.Change(load_config(tmp_path), graph, None), index)
    issue, = found.issues
    assert [part[1] for part in issue.parts] == [f'other.{suffix}:save']    # local's save is the writer


def test_typescript_same_reference_binds_to_the_function_and_not_a_data_role(tmp_path):
    _files(tmp_path, {'policy.ts': '''
        // flowguard: same ROUND ref
        export function reference(value: number) { return Math.round(value); }
        // flowguard: same ROUND
        export function copy(value: number) { return Math.round(value); }
        // flowguard: writers Account.status reference,other.ts:service.save
        // flowguard: together Account.status Account.changed except=other.ts:service.save(owner approved)
    ''', 'other.ts': '''
        export const service = { save(value: number) { return value; } };
    '''})
    with closing(build(tmp_path, tmp_path / 'map.sqlite', workers=1)) as graph:
        index = anchors.collect(graph)
        reference, copy = index.named('ROUND')
        assert (reference.kind, reference.qual, reference.owner) == ('sensor', 'reference', True)
        assert (copy.kind, copy.qual, copy.owner) == ('sensor', 'copy', False)
        assert not [issue for issue in index.issues if issue.name == 'ROUND']
        agreement, = index.named('Account.status')
        assert not [issue for issue in index.issues if issue.name == 'Account.status']
        assert [graph.node(position)['file'] for position in agreement.writers] == ['policy.ts', 'other.ts']
        assert agreement.writers == ('typescript/policy.ts:reference', 'typescript/other.ts:save')
        assert agreement.alone == ('typescript/other.ts:save(owner approved)',)


def test_typescript_positions_use_the_declared_holder_not_a_matching_method_tail(tmp_path):
    _files(tmp_path, {'prisma/schema.prisma': ACCOUNT_SCHEMA, 'policy.ts': '''
        // flowguard: writers Account.status other.ts:service.save
    ''', 'other.ts': '''
        export const service = {
          save(prisma: any) { return prisma.account.update({ where: { id: 1 }, data: { status: 'ready' } }); }
        };
        export const second = {
          save(prisma: any) { return prisma.account.update({ where: { id: 2 }, data: { status: 'ready' } }); }
        };
        export function save(prisma: any) {
          return prisma.account.update({ where: { id: 3 }, data: { status: 'ready' } });
        }
    '''})
    with closing(build(tmp_path, tmp_path / 'map.sqlite', workers=1)) as graph:
        index = anchors.collect(graph)
        assert not index.issues
        agreement, = index.named('Account.status')
        assert graph.node(agreement.writers[0])['line'] == 2
        rows = graph.writes('Account.status', by_name=True)
        assert {row['line'] for row in rows} == {2, 5, 8}
        # the writes of lines 5 and 8 are outside it, service.save's of line 2 is the writer's (the check of
        # `owner_writes`); the finding names a TS method by its own name, so both are its member `save`
        assert {row['line'] for row in rows if not owners._allowed(row, agreement.writers)} == {5, 8}
        issue, = owners.owner_writes(owners.Change(load_config(tmp_path), graph, None), index).issues
        assert [part[1] for part in issue.parts] == ['other.ts:save'] and issue.files == {'other.ts'}
        _files(tmp_path, {'policy.ts': '// flowguard: writers Account.status other.ts:missing.save\n'})
    with closing(build(tmp_path, tmp_path / 'map.sqlite', workers=1)) as graph:
        index = anchors.collect(graph)
        assert any(issue.code == 'position' and issue.level == 'red' and 'missing.save' in issue.message
                   for issue in index.issues)


def test_typescript_bare_function_and_ambiguous_holders_do_not_borrow_an_object_method(tmp_path):
    _files(tmp_path, {'policy.ts': '''
        // flowguard: writers Account.status save
        export const service = { save(value: number) { return value; } };
        export const second = { save(value: number) { return value + 1; } };
        export function save(value: number) { return value - 1; }
    '''})
    with closing(build(tmp_path, tmp_path / 'map.sqlite', workers=1)) as graph:
        index = anchors.collect(graph)
        agreement, = index.named('Account.status')
        assert not index.issues
        assert graph.node(agreement.writers[0])['line'] == 4
    _files(tmp_path, {'policy.ts': '''
        // flowguard: writers Account.status service.save
        export const service = { save(value: number) { return value; } };
        export const service = { save(value: number) { return value + 1; } };
    '''})
    with closing(build(tmp_path, tmp_path / 'map.sqlite', workers=1)) as graph:
        index = anchors.collect(graph)
        assert any(issue.code == 'position' and issue.level == 'red' and 'service.save' in issue.message
                   for issue in index.issues)


@pytest.mark.parametrize('suffix', ['py', 'ts'])
@pytest.mark.parametrize('role', ['writers', 'together'])
@pytest.mark.parametrize('missing', ['file', 'function'])
def test_new_positions_reject_missing_source_files_and_functions(tmp_path, suffix, role, missing):
    target = f'not-here.{suffix}:save' if missing == 'file' else f'other.{suffix}:missing'
    marker = '#' if suffix == 'py' else '//'
    comment = f'writers Account.status {target}' if role == 'writers' else \
        f'together Account.status Account.changed except={target}(owner approved)'
    _files(tmp_path, {f'policy.{suffix}': f'{marker} flowguard: {comment}\n',
                      f'other.{suffix}': 'def save(): pass\n' if suffix == 'py' else 'export function save() {}\n'})
    with closing(build(tmp_path, tmp_path / 'map.sqlite', workers=1)) as graph:
        index = anchors.collect(graph)
        issue, = [issue for issue in index.issues if issue.code == 'position']
    assert (issue.level, issue.file, issue.line, issue.name) == ('red', f'policy.{suffix}', 1, 'Account.status')
    assert target in issue.message


def test_a_historical_slice_keeps_positions_without_claiming_to_resolve_other_sources(tmp_path):
    _files(tmp_path, {'policy.py': '# flowguard: writers Account.status not-here.py:save\n'})
    index = anchors.collect_sources(tmp_path, [('policy.py', 'policy')])
    agreement, = index.named('Account.status')
    assert agreement.writers == ('not-here.py:save',)
    assert not [issue for issue in index.issues if issue.code == 'position']


@pytest.mark.parametrize('suffix', ['py', 'ts'])
@pytest.mark.parametrize('reverse', [False, True])
def test_splitting_a_mixed_agreement_keeps_one_registration_with_both_constraints(tmp_path, suffix, reverse):
    marker = '#' if suffix == 'py' else '//'
    module = 'policy' if suffix == 'py' else 'typescript/policy.ts'
    function = 'def save(): pass\n' if suffix == 'py' else 'export function save() {}\n'
    old = f'{marker} flowguard: owner Account.status writers={module}:save with=Account.changed on=update\n'
    separate = [f'{marker} flowguard: writers Account.status save\n',
                f'{marker} flowguard: together Account.status Account.changed on=update\n']
    if reverse:
        separate.reverse()
    registrations = []
    for comments in (old, ''.join(separate)):
        _files(tmp_path, {f'policy.{suffix}': comments + function})
        with closing(build(tmp_path, tmp_path / 'map.sqlite', workers=1)) as graph:
            index = anchors.collect(graph)
        agreement, = index.named('Account.status')
        assert not [issue for issue in index.issues if issue.name == 'Account.status']
        registrations.append((agreement.kind, agreement.name, agreement.module, agreement.writers,
                              agreement.pairs, agreement.on, agreement.alone))
    assert registrations == [('owner', 'Account.status', module, (module + ':save',),
                              ('Account.changed',), 'update', ())] * 2


def test_a_split_registration_still_checks_the_writer_and_the_required_partner(tmp_path):
    _files(tmp_path, {'prisma/schema.prisma': ACCOUNT_SCHEMA, 'policy.ts': '''
        // flowguard: writers Account.status save
        // flowguard: together Account.status Account.changed on=update
        export function save(prisma: any) {
          return prisma.account.update({ where: { id: 1 }, data: { status: 'ready' } });
        }
        export function rogue(prisma: any) {
          return prisma.account.update({ where: { id: 2 }, data: { status: 'ready' } });
        }
    '''})
    with closing(build(tmp_path, tmp_path / 'map.sqlite', workers=1)) as graph:
        index = anchors.collect(graph)
        assert not [issue for issue in index.issues if issue.name == 'Account.status']
        change = owners.Change(load_config(tmp_path), graph, None)
        assert {row['function'] for row in graph.writes('Account.status', by_name=True)} == {'save', 'rogue'}
        writers = owners.owner_writes(change, index)
        pairs = owners.owner_pairs(change, index)
    writer, = writers.issues
    assert [part[1] for part in writer.parts] == ['policy.ts:rogue']
    assert {issue.name for issue in pairs.issues} == {'pair:Account.status>Account.changed'}
    # both updates miss the partner
    assert sorted(part[1] for part in pairs.issues[0].parts) == ['policy.ts:rogue', 'policy.ts:save']


@pytest.mark.parametrize('suffix', ['py', 'ts'])
@pytest.mark.parametrize('reverse', [False, True])
def test_split_agreements_point_to_each_roles_own_comment(tmp_path, suffix, reverse):
    marker = '#' if suffix == 'py' else '//'
    field = 'account.status' if suffix == 'py' else 'Account.status'
    partner = 'account.changed' if suffix == 'py' else 'Account.changed'
    comments = [f'{marker} flowguard: writers {field} save', f'{marker} flowguard: together {field} {partner}']
    if reverse:
        comments.reverse()
    body = '''
        def save(db):
            db.execute("UPDATE account SET status = 'ready'")
        def rogue(db):
            db.execute("UPDATE account SET status = 'ready'")
    ''' if suffix == 'py' else '''
        export function save(prisma: any) {
          return prisma.account.update({ where: { id: 1 }, data: { status: 'ready' } });
        }
        export function rogue(prisma: any) {
          return prisma.account.update({ where: { id: 2 }, data: { status: 'ready' } });
        }
    '''
    _files(tmp_path, {f'policy.{suffix}': comments[0] + '\n' * 8 + comments[1] + '\n' + textwrap.dedent(body).lstrip(),
                      **({'prisma/schema.prisma': ACCOUNT_SCHEMA} if suffix == 'ts' else {})})
    with closing(build(tmp_path, tmp_path / 'map.sqlite', workers=1)) as graph:
        index = anchors.collect(graph)
        assert not index.issues
        raw = graph.file_facts(f'policy.{suffix}')['anchors']
        assert [row['line'] for row in raw] == [1, 9]
        change = owners.Change(load_config(tmp_path), graph, None)
        writers = owners.owner_writes(change, index)
        pairs = owners.owner_pairs(change, index)
        shown = owners.show_lines(load_config(tmp_path), graph, index, field)
    writer_line, pair_line = (9, 1) if reverse else (1, 9)
    assert len(writers.issues) == 1 and writers.issues[0].detail[0] == f'agreement: policy.{suffix}:{writer_line}'
    assert len(pairs.issues) == 1 and f'comment at policy.{suffix}:{pair_line}' in pairs.issues[0].step
    assert shown[0].startswith(f'owner {field} policy.{suffix}:{writer_line}; writers=')


def test_ambiguous_role_locations_are_labelled_as_canonical_registration(tmp_path):
    _files(tmp_path, {'policy.py': '''
        # flowguard: writers account.status save
        # flowguard: writers account.status other
        def rogue(db):
            db.execute("UPDATE account SET status = 'ready'")
    '''})
    with closing(build(tmp_path, tmp_path / 'map.sqlite', workers=1)) as graph:
        index = anchors.collect(graph)
        assert any(issue.code == 'owner' and issue.level == 'red' for issue in index.issues)
        found = owners.owner_writes(owners.Change(load_config(tmp_path), graph, None), index)
    assert len(found.issues) == 2
    assert all(issue.detail[0].startswith('agreement: canonical registration policy.py:') for issue in found.issues)


@pytest.mark.parametrize('comments', [
    ['writers Account.status save', 'writers Account.status save'],
    ['writers Account.status save', 'writers Account.status other'],
    ['together Account.status Account.changed', 'together Account.status Account.other'],
    ['together Account.status Account.changed on=create', 'together Account.status Account.changed on=update'],
    ['writers Account.status save', 'together Account.status Account.changed',
     'together Account.status Account.other'],
])
def test_repeated_or_conflicting_data_constraints_are_not_merged(tmp_path, comments):
    _files(tmp_path, {'policy.py': '\n'.join('# flowguard: ' + comment for comment in comments) +
            '\ndef save(): pass\ndef other(): pass\n'})
    with closing(build(tmp_path, tmp_path / 'map.sqlite', workers=1)) as graph:
        index = anchors.collect(graph)
    assert len(index.named('Account.status')) == len(comments)
    problems = [issue for issue in index.issues if issue.name == 'Account.status' and issue.code == 'owner']
    assert len(problems) == len(comments)
    assert all(issue.level == 'red' and 'repeated or incompatible data agreements' in issue.message
               for issue in problems)


def test_data_constraints_in_different_files_are_not_combined(tmp_path):
    _files(tmp_path, {'writer.py': '# flowguard: writers Account.status save\ndef save(): pass\n',
                      'pair.py': '# flowguard: together Account.status Account.changed\n'})
    with closing(build(tmp_path, tmp_path / 'map.sqlite', workers=1)) as graph:
        index = anchors.collect(graph)
    assert len(index.named('Account.status')) == 2
    assert any(issue.code == 'owner' and 'same file' in issue.message for issue in index.issues)


def test_old_spellings_keep_their_bindings_and_every_warm_index_read_uses_them(tmp_path, capsys):
    _files(tmp_path, {'policy.py': '''
        # flowguard: owner ROUND
        def reference(value: int) -> int:
            return value
        # flowguard: sensor ROUND
        def first(value: int) -> int:
            return value
        # flowguard: sensor ROUND
        def second(value: int) -> int:
            return value
        # flowguard: owner account.status writers=save with=account.changed alone=save(owner approved)
    '''})
    database = tmp_path / 'map.sqlite'
    from flowguard.intent import deprecation
    for warm in (False, True):
        start = deprecation.mark()
        with closing(build(tmp_path, database, workers=1)) as graph:
            if warm:
                assert graph.stats['parsed'] == 0
            index = anchors.collect(graph)
        agreement, = index.named('account.status')
        assert agreement.writers == ('save',)
        assert agreement.pairs == ('account.changed',)
        assert agreement.alone == ('save(owner approved)',)
        assert [(a.qual, a.owner) for a in index.named('ROUND')] == [
            ('reference', True), ('first', False), ('second', False)]
        # The warm read uses the old spellings as the cold one did; their notices print once in the process.
        assert set(deprecation.used(start)) == {'sensor', 'function owner', 'owner with writers= and with=', 'alone='}
        notices = capsys.readouterr().err
        if warm:
            assert notices == '', notices
            continue
        assert notices.count('deprecated: sensor ') == 1
        assert 'same NAME ref' in notices
        assert 'separate writers and together comments' in notices
        assert 'except=path:function(reason)' in notices


def test_old_foreign_function_owner_keeps_its_navigation_binding():
    facts = anchors.foreign_owners('// flowguard: owner ROUND\n', 'typescript/policy.ts', 'policy.ts')
    agreement, = facts['anchors']
    assert (agreement['kind'], agreement['qual'], agreement['owner']) == ('owner', '', False)


@pytest.mark.parametrize('comment', [
    'together Account.status Account.changed on=merge',
    'together Account.status Account.changed except=save(reason)',
    'writers Account.status ../outside.py:save',
    'writers Account.status /outside.py:save',
    'writers Account.status save extra',
])
def test_invalid_new_agreements_are_syntax_findings(comment):
    facts = _facts('# flowguard: ' + comment + '\n')
    assert not facts.get('anchors')
    assert facts['anchor_issues'][0]['level'] == 'red'
    assert facts['anchor_issues'][0]['code'] == 'syntax'


@pytest.mark.parametrize('source, expected', [
    ('''from typing import Annotated
# flowguard: same LIMIT(value: seconds)
def decision(value: Annotated[int, 'metres']) -> bool: return value > 0
''', 'unit'),
    ('''# flowguard: same LIMIT ref
def first(value: int) -> bool: return value > 0
# flowguard: same LIMIT ref
def second(value: int) -> bool: return value > 0
''', 'owner'),
    ('''# flowguard: same LIMIT
def first(value: int) -> bool: return value > 0
# flowguard: same LIMIT
def second(other: int) -> bool: return other > 0
''', 'identity'),
])
def test_new_names_do_not_relax_units_signatures_or_the_single_reference(tmp_path, source, expected):
    _files(tmp_path, {'policy.py': source})
    with closing(build(tmp_path, tmp_path / 'map.sqlite', workers=1)) as graph:
        index = anchors.collect(graph)
    assert any(issue.code == expected and issue.name == 'LIMIT' for issue in index.issues)
