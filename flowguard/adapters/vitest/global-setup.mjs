// The root project owns the observations directory and the final report. Its setup runs before vitest starts any
// worker and sets FLOWGUARD_VITEST_OBS, which vitest hands to the workers of both pools (forks and threads) with the
// rest of process.env; the recorders and the static test write into that folder. Its teardown runs after vitest's
// summary and prints the FlowGuard block there.
const builtin = typeof process.getBuiltinModule === 'function' ? process.getBuiltinModule.bind(process) : null;
const fs = builtin?.('fs'), path = builtin?.('path');
const read = fs?.readFileSync, exists = fs?.existsSync, remove = fs?.rmSync, mkdir = fs?.mkdirSync;
const spawn = builtin?.('child_process').spawnSync;
let observations = '';
let active = false;

export function setup(project) {
  if (!project.isRootProject()) return;
  active = true;
  if (!builtin) return;
  const plan = process.env.FLOWGUARD_VITEST_PLAN;
  observations = path.join(path.dirname(plan), `obs-${process.pid}-${Date.now()}`);
  mkdir(observations, { recursive: true });
  process.env.FLOWGUARD_VITEST_OBS = observations;
}

export function teardown() {
  if (!active) return;
  if (!builtin) {
    console.log('\nnot compared: this Node.js has no process.getBuiltinModule; call recording is unavailable');
    return;
  }
  const saved = path.join(observations, 'report.json');
  if (exists(saved)) {
    const { text, status } = JSON.parse(read(saved, 'utf8'));
    remove(observations, { recursive: true });
    if (text) console.log('\n' + text);
    if (status === 1) process.exitCode = 1;
    return;
  }
  const [command, ...prefix] = JSON.parse(process.env.FLOWGUARD_VITEST_PYTHON);
  const run = spawn(command, [...prefix, '-m', 'flowguard.intent.vitest', 'report', '--root', process.env.FLOWGUARD_VITEST_ROOT,
    '--plan', process.env.FLOWGUARD_VITEST_PLAN, '--observations', observations, '--package', process.env.FLOWGUARD_VITEST_PACKAGE], {
    encoding: 'utf8', maxBuffer: 64 * 1024 * 1024, env: { ...process.env, PYTHONIOENCODING: 'utf-8' },
  });
  const output = ((run.stdout || '') + (run.stderr || '')).trimEnd();
  if (run.error) throw run.error;
  if (run.status !== 0 && run.status !== 1) throw new Error(`FlowGuard report exit ${run.status}:\n${output}`);
  if (run.stdout.trim()) console.log('\n' + run.stdout.trimEnd());
  if (run.stderr.trim()) console.error(run.stderr.trimEnd());       // deprecated: lines
  if (run.status === 1) process.exitCode = 1;
}
