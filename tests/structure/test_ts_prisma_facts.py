"""TS/JS and Prisma/SQL map facts on fragments copied from a real TS/Prisma project.

The fragments live in tests/fixtures/planning_tool as `.txt` files (each names its source path and
line range) and are written into an isolated project under their real names. The expected writes
below were written by reading those fragments, not by running the reader.
"""
from contextlib import closing
from pathlib import Path
import shutil

import pytest

from flowguard.structure import build

FIXTURES = Path(__file__).resolve().parents[1] / 'fixtures' / 'planning_tool'
EMPLOYEE = 'backend/src/services/employee.service.ts'
TRANSFER = 'backend/src/services/employee-transfer.service.ts'
SYNC = 'backend/src/services/sync.service.ts'
SEED = 'backend/tests/integration/org-structure.routes.test.ts'
SYNTHETIC = 'synthetic/prisma-relations.ts'

CENTRAL_FIELDS = ('sapNumber', 'name', 'firstName', 'surname', 'email', 'orgUnitId', 'active', 'personnelSource',
                  'externalType', 'storageScope', 'personnelLifecycleState', 'centralSyncState', 'centralSyncError',
                  'centralSyncAttemptedAt')
SYNC_MARKS = ('centralSyncState', 'centralSyncError', 'centralSyncAttemptedAt')
LIFECYCLE = ('personnelLifecycleState', 'centralSyncState', 'centralSyncError', 'centralSyncAttemptedAt')
# (file, line of the call, model): fields the call really writes. Hand-written from the fragments.
TRUE_WRITES = {
    (EMPLOYEE, 19, 'Employee'): SYNC_MARKS,
    (EMPLOYEE, 25, 'Employee'): SYNC_MARKS,
    (EMPLOYEE, 32, 'Employee'): ('organizationalUnitId', 'authorityVersion', *SYNC_MARKS, 'personnelCommandKey'),
    (EMPLOYEE, 50, 'Employee'): ('id', 'name', 'firstName', 'surname', 'email', 'sapReference', 'supervisorId',
                                 'organizationalUnitId', 'startDate', 'endDate', 'employeeStatusId', 'resourceTypeId'),
    (EMPLOYEE, 50, 'UserRole'): ('role', 'employeeId'),
    (EMPLOYEE, 96, 'Employee'): ('name', 'firstName', 'surname', 'email', 'sapReference', 'supervisorId',
                                 'organizationalUnitId', 'startDate', 'endDate', 'employeeStatusId', 'resourceTypeId',
                                 'passwordHash', 'authorityVersion'),
    (EMPLOYEE, 123, 'Employee'): ('id', 'name', 'firstName', 'surname', 'email', 'sapReference', 'organizationalUnitId',
                                  'personnelSource', 'externalType', 'storageScope', 'personnelLifecycleState',
                                  'centralSyncState', 'personnelCommandKey', 'startDate', 'endDate', 'employeeStatusId',
                                  'resourceTypeId', 'passwordHash'),
    (EMPLOYEE, 123, 'UserRole'): ('role', 'employeeId'),
    (EMPLOYEE, 182, 'CentralEmployee'): CENTRAL_FIELDS,
    (EMPLOYEE, 184, 'CentralEmployee'): CENTRAL_FIELDS,
    (EMPLOYEE, 186, 'Employee'): LIFECYCLE,
    (EMPLOYEE, 193, 'Employee'): LIFECYCLE,
    (TRANSFER, 13, 'EmployeeTransfer'): SYNC_MARKS,
    (TRANSFER, 14, 'Employee'): SYNC_MARKS,
    (TRANSFER, 33, 'Employee'): ('organizationalUnitId', 'authorityVersion', *SYNC_MARKS, 'personnelCommandKey'),
    (TRANSFER, 38, 'EmployeeTransfer'): ('status', 'revision', 'sourceApprovalCommandKey', 'targetApprovalCommandKey',
                                         'decidedById', 'decidedAt', 'lastCommandKey', 'lastCommandAction', *SYNC_MARKS,
                                         'reason'),
    (TRANSFER, 44, 'AuditEvent'): ('domain', 'action', 'entityType', 'entityId', 'oldValue', 'newValue', 'actorId',
                                   'timestamp', 'contextId', 'idempotencyKey', 'severity'),
    (TRANSFER, 45, 'Notification'): ('recipientId', 'type', 'title', 'message', 'metadata'),
    (SYNC, 12, 'CentralEmployee'): ('sapNumber', 'name', 'firstName', 'surname', 'email', 'orgUnitId', 'active'),
    (SYNC, 25, 'CentralEmployee'): ('name', 'firstName', 'surname', 'email', 'orgUnitId'),
    (SYNC, 63, 'Employee'): ('name', 'firstName', 'surname', 'email', 'sapReference', 'organizationalUnitId', 'startDate',
                             'employeeStatusId', 'resourceTypeId'),
    (SYNC, 63, 'UserRole'): ('role', 'employeeId'),
    (SYNC, 85, 'UserRole'): ('*',),
    (SYNC, 89, 'Employee'): ('name', 'firstName', 'surname', 'email', 'organizationalUnitId'),
    (SEED, 5, 'AuthorityAssignment'): ('employeeId', 'definitionCode', 'domain', 'bindingKind', 'bindingId', 'identityKey',
                                       'sourceRef', 'bindingRootId', 'bindingMembersJson'),
    (SYNTHETIC, 5, 'EmployeeTransfer'): ('targetOrgUnitId', 'commandKey', 'employeeId', 'requestedById'),
    (SYNTHETIC, 16, 'EmployeeTransfer'): ('decidedById', 'status'),
    (SYNTHETIC, 20, 'UserRole'): ('employeeId',),
    (SYNTHETIC, 24, 'UserRole'): ('role', 'employeeId'),
    (SYNTHETIC, 24, 'Employee'): ('name', 'email', 'sapReference', 'startDate', 'employeeStatusId', 'resourceTypeId'),
    (SYNTHETIC, 40, 'Employee'): ('organizationalUnitId',),
    (SYNTHETIC, 41, 'UserRole'): ('*',),
}
UNCLEAR = {(SYNTHETIC, 45, 'Employee')}        # data: { ...changes }: the written fields are not visible
ORGANIZATION_WRITERS = {(EMPLOYEE, 32), (EMPLOYEE, 50), (EMPLOYEE, 96), (EMPLOYEE, 123), (TRANSFER, 33),
                        (SYNC, 63), (SYNC, 89), (SYNTHETIC, 40)}


@pytest.fixture(scope='module')
def planning(tmp_path_factory):
    root = tmp_path_factory.mktemp('planning') / 'pt'
    for path in FIXTURES.rglob('*.txt'):
        target = root / path.relative_to(FIXTURES).with_suffix('')
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)
    with closing(build(root, root.parent / 'map.sqlite', workers=1)) as graph:
        yield graph


def truth():
    return {(file, line, model, field) for (file, line, model), fields in TRUE_WRITES.items() for field in fields}


def test_prisma_writes_reach_eighty_percent_precision_and_recall(planning):
    rows = planning.writes()
    found = {(row['file'], row['call_line'], row['model'], row['field']) for row in rows
             if not row['unclear'] and row['how'] in ('prisma', 'sql')}
    expected = truth()
    precision = len(found & expected) / len(found)
    recall = len(found & expected) / len(expected)
    assert precision >= 0.8 and recall >= 0.8, (precision, recall, sorted(found - expected), sorted(expected - found))
    unclear = {(row['file'], row['call_line'], row['model']) for row in rows if row['unclear'] and row['how'] == 'prisma'}
    assert UNCLEAR <= unclear


def test_who_writes_a_field_excludes_where_select_and_plain_calls(planning):
    rows = planning.writes('Employee.organizationalUnitId')
    definite = {(row['file'], row['call_line']) for row in rows if not row['unclear']}
    assert definite == ORGANIZATION_WRITERS
    assert (TRANSFER, 14) not in definite          # only in `where` of markCentralState's updateMany
    assert (EMPLOYEE, 6) not in definite           # an object passed to syncEmployeeUpdateToCentral(...)
    by_column = {(row['file'], row['call_line']) for row in planning.writes('employees.organizational_unit_id')
                 if not row['unclear']}
    assert by_column == definite
    first = next(row for row in rows if row['file'] == EMPLOYEE and row['call_line'] == 96)
    assert (first['function'], first['kind'], first['db_column'], first['line']) == (
        'update', 'update', 'organizational_unit_id', 103)
    unclear = [row for row in rows if row['unclear']]
    assert [(row['file'], row['call_line'], row['field']) for row in unclear] == [(SYNTHETIC, 45, '?')]


def test_connect_and_nested_writes_follow_the_schema_relation(planning):
    rows = [row for row in planning.writes() if row['file'] == SYNTHETIC]
    kinds = {(row['call_line'], row['model'], row['field']): row['kind'] for row in rows}
    assert kinds[(5, 'EmployeeTransfer', 'employeeId')] == 'connect'
    assert kinds[(16, 'EmployeeTransfer', 'decidedById')] == 'disconnect'
    assert kinds[(20, 'UserRole', 'employeeId')] == 'connect'            # the key is on the other side
    assert kinds[(24, 'UserRole', 'employeeId')] == 'connectOrCreate'
    assert kinds[(24, 'Employee', 'email')] == 'nested:connectOrCreate'
    assert kinds[(40, 'Employee', 'organizationalUnitId')] == 'sql:update'
    assert kinds[(41, 'UserRole', '*')] == 'sql:delete'
    assert not any(row['call_line'] in (49, 50) for row in rows)           # Map.delete(key) is not Prisma
    nested = next(row for row in planning.writes() if row['file'] == EMPLOYEE and row['call_line'] == 50
                  and row['model'] == 'UserRole' and row['field'] == 'employeeId')
    assert nested['kind'] == 'nested:create' and nested['nested']


def test_property_assignments_are_writes_by_name_only_on_request(planning):
    assert not [row for row in planning.writes('committed.added')]
    named = planning.writes('added', by_name=True)
    assert named and {row['how'] for row in named} == {'name'} and all(row['model'] is None for row in named)
    assert {row['line'] for row in named if row['file'] == SYNC} == {23, 77}


def test_typescript_catch_clauses_separate_handing_on_from_fallbacks(planning):
    rows = {(row['file'], row['line']): row for row in planning.handlers(language='typescript')}
    handed = {key: row['propagates'] for key, row in rows.items() if not row['non_raising']}
    assert handed[('backend/src/api/routes/absence.routes.ts', 11)] == ['next']
    assert handed[(EMPLOYEE, 23)] == ['throw'] and handed[(EMPLOYEE, 68)] == ['throw']
    assert handed[(EMPLOYEE, 191)] == ['throw']
    fallbacks = {key for key, row in rows.items() if row['non_raising']}
    assert fallbacks == {(SYNC, 45), (SYNC, 111)}
    row = rows[(SYNC, 45)]
    assert (row['kind'], row['type'], row['name'], row['function']) == ('catch', 'any', 'error', 'SyncService.commitSync')
    assert row['key'] == SYNC + ':SyncService.commitSync:any' and not row['raises']
    assert planning.query_coverage()['complete']


def test_literal_groups_show_the_label_drift_and_skip_keys_logs_and_errors(planning):
    groups = {group['key']: group['spellings'] for group in planning.literal_groups()}
    drift = groups['myorganization']
    assert set(drift) == {'My Organization', 'My organization'}
    assert {(row['file'], row['context']) for row in drift['My Organization']} == {
        ('backend/src/services/authority/organization-navigation.ts', 'union'),
        ('backend/src/services/authority/organization-navigation.ts', 'return')}
    assert {row['context'] for row in drift['My organization']} == {'union', 'set'}
    values = {row['value'] for row in planning.literals()}
    assert 'TEAM' not in values and 'DEPARTMENT' not in values           # object keys
    assert not any('synchronization failed' in value for value in values)  # error messages
    assert not any(value.startswith('Sync local') for value in values)    # logger.error(...)
    assert 'My Unit' in values and 'myunit' not in groups                  # one spelling: no group


def test_named_typescript_functions_have_python_style_shapes(planning):
    functions = planning.functions(language='typescript')
    owner = functions['typescript/backend/src/services/utilization/utilization-calculation.ts:countWorkingDays']
    copy = functions['typescript/backend/src/services/org-unit-summary.service.ts:countWorkingDaysLocal']
    other = functions['typescript/backend/src/services/utilization/utilization-calculation.ts:normalizeToUtcMidnight']
    from flowguard.structure.store import shape_list
    sketch = lambda node: set(shape_list(planning.con.execute('SELECT shape FROM node WHERE id=?', (node['id'],)).fetchone()[0]))
    assert sketch(owner) and sketch(owner) == sketch(copy) and owner['fp'] == copy['fp']
    assert len(sketch(owner) & sketch(other)) / len(sketch(owner) | sketch(other)) < 0.5
    anonymous = [node for node in functions.values() if '<anonymous' in node['qual']]
    assert anonymous and all(not sketch(node) for node in anonymous)


def test_schema_and_sql_descriptions_list_the_missing_columns(planning):
    files = {schema['file']: schema for schema in planning.schemas()}
    central = files['backend/prisma/central/schema.prisma']
    employee = next(model for model in central['models'] if model['name'] == 'CentralEmployee')
    org = next(field for field in employee['fields'] if field['name'] == 'orgUnitId')
    assert (employee['table'], org['column']) == ('central_employees', 'org_unit_id')
    relation = next(field for field in employee['fields'] if field['name'] == 'orgUnit')['relation']
    assert relation == dict(name='', fields=['orgUnitId'], references=['id'])
    init = files['backend/prisma/central/init-azure-sql.sql']
    assert [table['name'] for table in init['tables']] == ['central_org_units', 'central_employees']
    gaps = planning.schema_gaps()
    columns = [gap for gap in gaps if gap['kind'] == 'sql' and gap['description'] == 'backend/prisma/central/init-azure-sql.sql']
    assert [(gap['table'], gap['missing'], gap['extra']) for gap in columns] == [('central_employees', [
        'central_sync_attempted_at', 'central_sync_error', 'central_sync_state', 'external_type',
        'personnel_lifecycle_state', 'personnel_source', 'storage_scope'], [])]
    tables = [gap['table'] for gap in gaps if gap['kind'] == 'sql-table']
    assert tables == ['central_lending_assignments']
    migrations = [gap for gap in gaps if gap['description'] == 'backend/prisma/central/migrations/']
    assert migrations == []                       # CREATE + ALTER TABLE ADD in order: complete
    assert planning.keys(kind='column', value='central_employees.org_unit_id')


def test_show_answers_who_writes_a_model_field(planning, capsys):
    from flowguard.intent.cli import main
    assert main(['--root', str(planning.root), 'show', 'Employee.organizationalUnitId']) == 0
    lines = [line for line in capsys.readouterr().out.splitlines() if line.startswith('writes ')]
    assert len(lines) == len(ORGANIZATION_WRITERS) + 1
    assert any(line.startswith('writes Employee.organizationalUnitId backend/src/services/employee.service.ts:103 (call line 96) update')
               for line in lines)
    assert lines[-1].startswith('writes Employee.? synthetic/prisma-relations.ts:45 patch (update; unclear:')
    assert main(['--root', str(planning.root), 'show', 'markCentralState']) == 0
    assert 'employee-transfer.service.ts:markCentralState backend/src/services/employee-transfer.service.ts:6' in capsys.readouterr().out


def test_configured_names_also_hand_a_caught_error_on(tmp_path):
    from flowguard.intent.config import load_config
    source = ('export function run(res: any, sendError: any) {\n'
              '  try { work(); } catch (err) { reportFailure(res, err); }\n'
              '  try { work(); } catch (err) { sendError(err); }\n'
              '  try { work(); } catch (err) { reportFailure(err); }\n}\n')
    (tmp_path / 'a.ts').write_text(source)
    with closing(build(tmp_path, tmp_path / 'map.sqlite', workers=1)) as graph:
        outcome = [(row['line'], row['non_raising'], row['propagates']) for row in graph.handlers()]
        assert outcome == [(2, True, []), (3, False, ['sendError']), (4, True, [])]   # a parameter receives err
    (tmp_path / 'pyproject.toml').write_text('[tool.flowguard]\npropagate = ["reportFailure"]\n')
    assert load_config(tmp_path).root == tmp_path.resolve()
    with closing(build(tmp_path, tmp_path / 'map.sqlite', workers=1)) as graph:
        outcome = [(row['line'], row['non_raising'], row['propagates']) for row in graph.handlers()]
        assert outcome == [(2, True, []), (3, False, ['sendError']), (4, False, ['reportFailure'])]
