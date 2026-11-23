"""Agreements read what the code writes: a JS/TS, SQL or Python bool or null under either spelling (PTW-G55-2), and
each element of a Python tuple, list, starred, `for` or `with` target (PEMEL17-4).

The fixtures have the shapes the two projects reported on 5.0.1: Planning Tool's `Employee.planningEnabled` agreement
(`prisma/schema.prisma`, the services' creates, the seed creates without the field, the legacy mirror under
`except=`) and PEMEL Studio's `runner.py` and `w.py`. Each project commits its baseline first; `check --static`
reports what the working tree adds, `--all` also what the baseline already had.
"""
import pytest

from tests.intent_engine.test_static_check import _commit, _flowguard, _lines, _static, _write

SCHEMA = '''
    datasource db {
      provider = "sqlserver"
      url      = env("DATABASE_URL")
    }

    model Employee {
      id              String  @id @default(uuid())
      name            String
      planningEnabled Boolean @default(false)
    }
'''
SEED = '''
    import { PrismaClient } from '@prisma/client';
    const prisma = new PrismaClient();
    async function main() {
      await prisma.employee.create({ data: { name: 'Seed A' } });
      await prisma.employee.upsert({ where: { id: 'b' }, update: {}, create: { name: 'Seed B' } });
    }
    main();
'''
SERVICE = '''
    import { PrismaClient } from '@prisma/client';
    const prisma = new PrismaClient();

    // flowguard: together Employee.name Employee.planningEnabled=%s on=create except=src/sync.ts:mirrorCentral(mirror of an existing central person stays disabled)
    export async function createEmployee(name: string) {
      return prisma.employee.create({ data: { name, planningEnabled: true } });
    }
'''
SYNC = '''
    import { PrismaClient } from '@prisma/client';
    const prisma = new PrismaClient();
    export async function mirrorCentral(name: string) {
      return prisma.employee.create({ data: { name, planningEnabled: false } });
    }
'''
IMPORT = '''
    export async function importEmployee(name: string) {
      return prisma.employee.create({ data: { name, planningEnabled: true } });
    }
'''
DISABLED = '''
    export async function addDisabled(name: string) {
      return prisma.employee.create({ data: { name, planningEnabled: false } });
    }
'''
SEED_TEAM = '''
    export async function seedTeam() {
      await prisma.employee.create({ data: { name: 'Seed C' } });
    }
'''


@pytest.mark.parametrize('spelled', ['true', 'True'])
def test_a_typescript_true_holds_a_together_value_spelled_true_or_True(tmp_path, spelled):
    # PTW-G55-2: 5.0.1 compared `str(True)` with the comment's `true`, so a correct new import was red.
    _commit(tmp_path, {'package.json': '{"name":"g55","private":true,"type":"module"}\n', 'prisma/schema.prisma': SCHEMA,
                       'prisma/seed.ts': SEED, 'src/employee.service.ts': SERVICE % spelled, 'src/sync.ts': SYNC})
    service = (tmp_path / 'src/employee.service.ts').read_text(encoding='utf-8')
    _write(tmp_path, {'src/employee.service.ts': service + IMPORT})
    code, text = _static(tmp_path)
    assert code == 0 and not _lines(text, 'red: '), text
    # The seed creates that omit the field were already there: before, and the services' creates are not.
    code, text = _static(tmp_path, '--all')
    assert _lines(text, 'before: ') == [
        'before: together Employee.name at seed.ts:main was broken at task start -> leave it unless your task is about it'], text
    # A create writing false, and a new seed create without the field, are red; the mirror under except= is not.
    seed = (tmp_path / 'prisma/seed.ts').read_text(encoding='utf-8')
    _write(tmp_path, {'src/employee.service.ts': service + IMPORT + DISABLED, 'prisma/seed.ts': seed + SEED_TEAM})
    code, text = _static(tmp_path)
    assert code == 1 and sorted(_lines(text, 'red: ')) == [
        f'red: together Employee.name: employee.service.ts:addDisabled writes Employee.name without '
        f'Employee.planningEnabled={spelled} (creates only) -> also write Employee.planningEnabled={spelled} in addDisabled',
        f'red: together Employee.name: seed.ts:seedTeam writes Employee.name without '
        f'Employee.planningEnabled={spelled} (creates only) -> also write Employee.planningEnabled={spelled} in seedTeam'], text


JOB = '''
    # flowguard: together Job.phase Job.active=%s,Job.owner=%s
    # flowguard: together jobs.phase jobs.active=%s
    class Job:
        def open(self):
            self.phase = 'open'
            self.active = True
            self.owner = None


    def reopen(db, job_id):
        db.execute("UPDATE jobs SET phase = 'open', active = TRUE WHERE id = ?", (job_id,))
'''
JOB_CHANGES = '''

    def close(job: Job):
        job.phase = 'closed'
        job.active = True
        job.owner = None


    def pause(job: Job):
        job.phase = 'paused'
        job.active = False
        job.owner = None


    def claim(job: Job):
        job.phase = 'claimed'
        job.active = True
        job.owner = 'me'


    def stop(db, job_id):
        db.execute("UPDATE jobs SET phase = 'stopped', active = FALSE WHERE id = ?", (job_id,))


    def restart(db, job_id):
        db.execute("UPDATE jobs SET phase = 'open', active = true WHERE id = ?", (job_id,))
'''


@pytest.mark.parametrize('true, null', [('true', 'null'), ('True', 'None')])
def test_a_python_or_sql_bool_or_none_holds_a_together_value_in_either_spelling(tmp_path, true, null):
    # A Python `True`/`None` and a SQL `TRUE`/`true` are the same values as `=true`/`=True` and `=null`/`=None`;
    # `False` holds neither true spelling, and a string `'me'` holds no null.
    _commit(tmp_path, {'jobs.py': JOB % (true, null, true)})
    _write(tmp_path, {'jobs.py': (JOB % (true, null, true)) + JOB_CHANGES})
    code, text = _static(tmp_path)
    assert code == 1 and sorted(_lines(text, 'red: ')) == [
        f'red: together Job.phase: jobs.py:claim writes Job.phase without Job.owner={null} -> also write Job.owner={null} in claim',
        f'red: together Job.phase: jobs.py:pause writes Job.phase without Job.active={true} -> also write Job.active={true} in pause',
        f'red: together jobs.phase: jobs.py:stop writes jobs.phase without jobs.active={true} -> also write jobs.active={true} in stop',
    ], text


RUNNER = '''
    # flowguard: together Runner.task_id Runner.operation
    class Runner:
        def __init__(self):
            self.task_id = ""
            self.operation = ""

        def start(self):
            %s
'''


def test_a_tuple_write_is_listed_by_show_and_holds_or_misses_its_partner(tmp_path):
    # PEMEL17-4: 5.0.1 recorded `self.task_id, self.operation = ...` as no write: show left it out, and a tuple that
    # dropped the partner gave 0 red.
    _commit(tmp_path, {'runner.py': RUNNER % 'self.task_id, self.operation = "id", "parse"'})
    code, text = _flowguard(tmp_path, 'show', 'Runner.task_id')
    assert _lines(text, 'writes ') == ['writes Runner.task_id runner.py:4 Runner.__init__ (assign)',
                                       'writes Runner.task_id runner.py:8 Runner.start (assign)'], text
    _write(tmp_path, {'runner.py': RUNNER % 'self.task_id, self.unrelated = "id", "parse"'})
    code, text = _static(tmp_path)
    assert code == 1 and _lines(text, 'red: ') == [
        'red: together Runner.task_id: runner.py:Runner.start writes Runner.task_id without Runner.operation '
        '-> also write Runner.operation in start'], text
    for held in ('self.task_id, (self.unrelated, self.operation) = "id", ("x", "parse")',
                 '[self.task_id, *self.operation] = "id", "parse"',
                 'for self.task_id, self.operation in self.queue(): pass'):
        _write(tmp_path, {'runner.py': RUNNER % held})
        code, text = _static(tmp_path)
        assert code == 0 and not _lines(text, 'red: '), (held, text)


JOB_WRITERS = '''
    # flowguard: writers Job.state Job.start
    import threading


    class Job:
        def __init__(self):
            self.state = "new"

        def start(self):
            self.state = "run"

        def stop(self):
            %s
'''


def test_a_tuple_loop_or_with_write_outside_its_writers_is_red(tmp_path):
    _commit(tmp_path, {'w.py': JOB_WRITERS % 'pass'})
    for statement in ('self.state, self.code = "stop", 0', 'for self.state in ("a", "b"): pass',
                      'with threading.Lock() as (self.code, self.state): pass'):
        _write(tmp_path, {'w.py': JOB_WRITERS % statement})
        code, text = _static(tmp_path)
        assert code == 1 and _lines(text, 'red: ') == [
            'red: writers Job.state: w.py:Job.stop writes Job.state outside Job.start -> call Job.start instead'], (statement, text)
