// FlowGuard vitest adapter: before the tests, a fresh folder for this run's observations; after them,
// Python reads the observations and prints FlowGuard's lines. Red sets the exit status to 1.
import fs from 'node:fs';
import path from 'node:path';
import { spawnSync } from 'node:child_process';

let observations = '';

export function setup() {
  const plan = process.env.FLOWGUARD_VITEST_PLAN;
  observations = path.join(path.dirname(plan), `obs-${process.pid}-${Date.now()}`);
  fs.mkdirSync(observations, { recursive: true });
  process.env.FLOWGUARD_VITEST_OBS = observations;
}

export function teardown() {
  const [command, ...prefix] = JSON.parse(process.env.FLOWGUARD_VITEST_PYTHON);
  const run = spawnSync(command, [...prefix, '-m', 'flowguard.intent.vitest', 'report', '--root', process.env.FLOWGUARD_VITEST_ROOT,
    '--plan', process.env.FLOWGUARD_VITEST_PLAN, '--observations', observations], {
    encoding: 'utf8', maxBuffer: 64 * 1024 * 1024, env: { ...process.env, PYTHONIOENCODING: 'utf-8' },
  });
  const output = ((run.stdout || '') + (run.stderr || '')).trimEnd();
  if (run.error) throw run.error;
  if (run.status !== 0 && run.status !== 1) throw new Error(`FlowGuard report exit ${run.status}:\n${output}`);
  if (output) console.log('\n' + output);
  if (run.status === 1) process.exitCode = 1;
}
