// FlowGuard vitest adapter: the one test case of FlowGuard's own vitest project, which index.mjs adds to the run
// after the project's tests (sequence.groupOrder). Python judges this run's observations as the teardown would;
// a red fails this test, so the red is in vitest's own results (JSON, junit), not only in the exit status. The
// text and status are saved for the teardown, which prints them after the summary. `test` is a global here.
import { spawnSync } from 'node:child_process';

test('FlowGuard execution side', () => {
  const [command, ...prefix] = JSON.parse(process.env.FLOWGUARD_VITEST_PYTHON);
  const run = spawnSync(command, [...prefix, '-m', 'flowguard.intent.vitest', 'report', '--root', process.env.FLOWGUARD_VITEST_ROOT,
    '--plan', process.env.FLOWGUARD_VITEST_PLAN, '--observations', process.env.FLOWGUARD_VITEST_OBS,
    '--package', process.env.FLOWGUARD_VITEST_PACKAGE, '--in-test'], {
    encoding: 'utf8', maxBuffer: 64 * 1024 * 1024, env: { ...process.env, PYTHONIOENCODING: 'utf-8' },
  });
  const output = ((run.stdout || '') + (run.stderr || '')).trimEnd();
  if (run.error) throw run.error;
  if (run.status !== 0 && run.status !== 1) throw new Error(`FlowGuard report exit ${run.status}:\n${output}`);
  if (run.status === 1) throw new Error('FlowGuard found red in the execution side:\n' + output);
}, 600000);
