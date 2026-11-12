// FlowGuard vitest adapter: the one test case of FlowGuard's own vitest project, which index.mjs adds to the run
// after the project's tests (sequence.groupOrder). Python judges this run's observations as the teardown would and
// saves the block, its status and the number of reds the static test did not already fail on; this test fails on
// those reds with one line, so they are in vitest's own results (JSON, junit) too. The teardown prints the block
// after vitest's summary. `test` is a global here.
const { spawnSync } = process.getBuiltinModule('child_process');
const { existsSync, readFileSync } = process.getBuiltinModule('fs');
const { join } = process.getBuiltinModule('path');

test('FlowGuard execution side', () => {
  const [command, ...prefix] = JSON.parse(process.env.FLOWGUARD_VITEST_PYTHON);
  const run = spawnSync(command, [...prefix, '-m', 'flowguard.intent.vitest', 'report', '--root', process.env.FLOWGUARD_VITEST_ROOT,
    '--plan', process.env.FLOWGUARD_VITEST_PLAN, '--observations', process.env.FLOWGUARD_VITEST_OBS,
    '--package', process.env.FLOWGUARD_VITEST_PACKAGE, '--in-test'], {
    encoding: 'utf8', maxBuffer: 64 * 1024 * 1024, env: { ...process.env, PYTHONIOENCODING: 'utf-8' },
  });
  const output = ((run.stdout || '') + (run.stderr || '')).trimEnd();
  const saved = join(process.env.FLOWGUARD_VITEST_OBS, 'report.json');
  if (run.error) throw run.error;
  // a report that did not finish (Python exits 1 on an error too) saved nothing: its output says why
  if ((run.status !== 0 && run.status !== 1) || !existsSync(saved)) throw new Error(`FlowGuard report exit ${run.status}:\n${output}`);
  const { red } = JSON.parse(readFileSync(saved, 'utf8'));
  if (red) {
    // One line: what the reds are is the block's job, printed after the summary.
    const error = new Error(`FlowGuard: ${red} red, see the FlowGuard block at the end`);
    error.stack = error.message;
    throw error;
  }
}, 600000);
